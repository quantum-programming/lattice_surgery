"""Finite-factory DoubleTimeSlice No_Top / No_Kink scheduling.

Layout matches Allocator's outer/naive allocation (one or two physical layers).
Two-terminal No_Kink routing ports the C++ BFS, including neighbor ordering,
earliest available endpoint slices, endpoint directions, and factory cooldown.
MAGIC_MZ3/MZ4 use horizontal attachments for every terminal, like MAGIC_MZZ.

Multibody routing is a heuristic: choose a nearby available factory by BFS from
the factory candidates to the first data terminal, compute pairwise BFS paths,
fix one attachment per terminal from its shortest incident connection, then
recompute conflicting paths and apply Kruskal. Finally remove physical cycles
and prune nonterminal leaves. The factory remains fixed throughout the tree.
This is neither an exact Steiner solver nor a model of kink-compatible trees.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import heapq
from math import isqrt
from typing import Iterable

from compute_ignore_topology import Instruction, prepare_look_ahead

TimePosition = tuple[int, int]
Edge = tuple[TimePosition, TimePosition]


@dataclass
class Layout:
    width: int
    height: int
    layer_count: int
    data_positions: tuple[int, ...]
    factories: tuple[int, ...]
    neighbors: tuple[tuple[int, ...], ...] = field(init=False, repr=False)
    ports: tuple[tuple[tuple[int, ...], ...], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        reserved = set(self.data_positions) | set(self.factories)
        neighbors = []
        for pos in range(self.chip_size):
            x, y, z = self.coordinates(pos)
            candidates = (
                (x - 1, y, z), (x + 1, y, z), (x, y - 1, z),
                (x, y + 1, z), (x, y, z - 1), (x, y, z + 1),
            )
            neighbors.append(tuple(
                self.position(nx, ny, nz) for nx, ny, nz in candidates
                if 0 <= nx < self.width and 0 <= ny < self.height
                and 0 <= nz < self.layer_count
                and self.position(nx, ny, nz) not in reserved
            ))
        self.neighbors = tuple(neighbors)
        self.ports = tuple(
            tuple(tuple(p for p in adjacent if self.direction(pos, p) == axis) for axis in (0, 1))
            for pos, adjacent in enumerate(self.neighbors)
        )

    @property
    def chip_size(self) -> int:
        return self.width * self.height * self.layer_count

    def position(self, x: int, y: int, z: int) -> int:
        return (z * self.height + y) * self.width + x

    def coordinates(self, pos: int) -> tuple[int, int, int]:
        return pos % self.width, (pos // self.width) % self.height, pos // (self.width * self.height)

    def direction(self, pos: int, other: int) -> int:
        a, b = self.coordinates(pos), self.coordinates(other)
        if sum(abs(x - y) for x, y in zip(a, b)) != 1:
            raise ValueError("Positions are not spatially adjacent")
        return next(axis for axis in range(3) if a[axis] != b[axis])

    @classmethod
    def naive_outer(cls, data_count: int, layer_count: int = 2) -> Layout:
        if layer_count not in (1, 2):
            raise ValueError("Physical layer count must be 1 or 2")
        size_2d = isqrt(data_count)
        size_2d += size_2d * size_2d < data_count
        size = isqrt(data_count // layer_count)
        size += size * size * layer_count < data_count
        width = size * 2 + 3
        position = lambda x, y, z: (z * width + y) * width + x
        data = tuple(
            position(2 + 2 * x, 2 + 2 * y, z)
            for x in range(size) for y in range(size) for z in range(layer_count)
        )[:data_count]
        factories = tuple(
            position(x, y, z)
            for x in range(width) for y in range(width)
            if (x in (0, width - 1) or y in (0, width - 1)) and (x + y) % 2 == 0
            for z in range(layer_count)
        )[:4 * (size_2d + 1)]
        return cls(width, width, layer_count, data, factories)


@dataclass(frozen=True)
class Route:
    nodes: tuple[TimePosition, ...]
    edges: tuple[Edge, ...]
    terminals: tuple[TimePosition, ...]  # In instruction target order.
    window_end: int


@dataclass
class ScheduleResult:
    total_code_beats: int
    instructions: list[Instruction]
    routes: list[Route]
    layout: Layout
    magic_prep_time: int
    routing: str

    def compute_circuit_volume(self) -> int:
        """Generalize C++ ScheduleResultBase::compute_circuit_volume to trees.

        Count data pillars for the full schedule, unique ancillary time-position
        cells in each route, and preparation time once per magic instruction.
        All terminals are excluded from routing volume: data endpoints are
        already in the pillars; factory endpoints are excluded by the C++
        finite-factory convention. For two-terminal gates this is exactly
        total_time * data_count + sum(path.length() - 2) + magic preparation.
        Temporal occurrences of the same ancillary position count separately.
        """
        pillars = self.total_code_beats * len(self.layout.data_positions)
        routing = sum(len(set(route.nodes) - set(route.terminals)) for route in self.routes)
        preparation = self.magic_prep_time * sum(-1 in inst.target_ids for inst in self.instructions)
        return pillars + routing + preparation


class NoKinkRouter:
    def __init__(self, layout: Layout, magic_prep_time: int):
        self.layout = layout
        self.size = layout.chip_size
        self.elapsed = 1
        self.until = [[-1] * self.size for _ in range(2)]
        self.blocked = bytearray(2 * self.size)
        self.option_cache: dict[tuple[tuple[int, ...], int], dict[int, int]] = {}
        self.visited = [0] * (2 * self.size)
        self.parents = [0] * (2 * self.size)
        self.search_id = 0
        # Vertex offsets 0 / size represent the past / current time slice.
        self.adjacency = tuple(
            (pos + (1 - layer) * self.size,)
            + tuple(p + layer * self.size for p in layout.neighbors[pos])
            for layer in range(2) for pos in range(self.size)
        )
        for factory in layout.factories:
            self.occupy(factory, magic_prep_time)

    def occupy(self, pos: int, lifetime: int) -> None:
        self.option_cache.clear()
        # Exact absolute-time equivalent of the two C++ LifetimeArrays.
        for offset, duration in ((0, (lifetime + 1) // 2), (1, lifetime // 2)):
            timing = self.elapsed - 1 + offset
            if duration:
                self.until[timing & 1][pos] = max(
                    self.until[timing & 1][pos], timing + 2 * (duration - 1),
                )
            self.blocked[offset * self.size + pos] = self.until[timing & 1][pos] >= timing

    def reserve(self, timing: int, pos: int) -> None:
        self.option_cache.clear()
        self.until[timing & 1][pos] = max(self.until[timing & 1][pos], timing)
        self.blocked[(timing - self.elapsed + 1) * self.size + pos] = 1

    def wait(self) -> None:
        self.option_cache.clear()
        self.elapsed += 1
        for offset in range(2):
            timing = self.elapsed - 1 + offset
            self.blocked[offset * self.size:(offset + 1) * self.size] = bytearray(
                end >= timing for end in self.until[timing & 1]
            )

    @staticmethod
    def directions(inst: Instruction, index: int) -> tuple[int, ...]:
        if inst.gate == "CX":
            return (index,)
        return (0, 1) if inst.gate == "MAGIC_MOVE" else (0,)

    def terminal_options(self, inst: Instruction, index: int) -> dict[int, int]:
        target = inst.target_ids[index]
        directions = self.directions(inst, index)
        cache_key = directions, target
        if cache_key in self.option_cache:
            return self.option_cache[cache_key]
        positions = self.layout.factories if target == -1 else (self.layout.data_positions[target],)
        for offset in range(2):
            options = {}
            for pos in positions:
                terminal = pos + offset * self.size
                if self.blocked[terminal]:
                    continue
                for direction in directions:
                    for neighbor in self.layout.ports[pos][direction]:
                        vertex = neighbor + offset * self.size
                        if not self.blocked[vertex]:
                            options.setdefault(vertex, terminal)
            if options:
                self.option_cache[cache_key] = options
                return options
        self.option_cache[cache_key] = {}
        return {}

    def pair_path(self, starts: dict[int, int], goals: dict[int, int]) -> list[int]:
        if not starts or not goals:
            return []
        self.search_id += 1
        stamp = self.search_id
        visited, parent = self.visited, self.parents
        blocked, adjacency = self.blocked, self.adjacency
        for vertex, terminal in starts.items():
            visited[vertex] = stamp
            parent[vertex] = terminal
        queue = deque(starts)
        while queue:
            vertex = queue.popleft()
            if vertex in goals:
                path = [goals[vertex], vertex]
                while path[-1] not in starts:
                    path.append(parent[path[-1]])
                path.append(starts[path[-1]])
                path.reverse()
                return path
            for neighbor in adjacency[vertex]:
                if not blocked[neighbor] and visited[neighbor] != stamp:
                    visited[neighbor] = stamp
                    parent[neighbor] = vertex
                    queue.append(neighbor)
        return []

    def route(self, inst: Instruction) -> Route | None:
        options = [self.terminal_options(inst, i) for i in range(len(inst.target_ids))]
        if not all(options):
            return None
        if len(options) == 2:
            path = self.pair_path(*options)
            if not path:
                return None
            return self.decode(path, list(zip(path, path[1:])), (path[0], path[-1]))

        # Bind one factory; never treat distinct factories as one terminal.
        initial = self.pair_path(options[0], options[1])
        if not initial:
            return None
        factory = initial[0]
        options[0] = {v: t for v, t in options[0].items() if t == factory}
        pairs = []
        for i in range(len(options)):
            for j in range(i + 1, len(options)):
                path = self.pair_path(options[i], options[j])
                if path:
                    pairs.append((len(path), i, j, path))
        pairs.sort()
        # A common attachment makes terminals leaves in the union of paths.
        anchors = {}
        for _, i, j, path in pairs:
            anchors.setdefault(i, (path[1], path[0]))
            anchors.setdefault(j, (path[-2], path[-1]))
        if len(anchors) != len(options):
            return None
        connections = []
        for _, i, j, path in pairs:
            if (path[1], path[0]) != anchors[i] or (path[-2], path[-1]) != anchors[j]:
                path = self.pair_path(dict([anchors[i]]), dict([anchors[j]]))
            if path:
                connections.append((len(path), i, j, path))
        connections.sort()
        components = list(range(len(options)))
        def root(index: int) -> int:
            while index != components[index]:
                index = components[index]
            return index
        edges = set()
        for _, i, j, path in connections:
            a, b = root(i), root(j)
            if a != b:
                components[a] = b
                edges.update(tuple(sorted(edge)) for edge in zip(path, path[1:]))
        if len({root(i) for i in range(len(options))}) != 1:
            return None
        terminals = tuple(anchors[i][1] for i in range(len(options)))
        nodes, edges = self.prune_tree(edges, terminals)
        return self.decode(nodes, edges, terminals)

    @staticmethod
    def prune_tree(edges: set[tuple[int, int]], terminals: tuple[int, ...]):
        graph: dict[int, set[int]] = {}
        for a, b in sorted(edges):
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
        # Deterministic spanning tree of the physical union removes cycles.
        tree = {vertex: set() for vertex in graph}
        seen = {terminals[0]}
        queue = deque(seen)
        while queue:
            a = queue.popleft()
            for b in sorted(graph[a]):
                if b not in seen:
                    seen.add(b)
                    tree[a].add(b)
                    tree[b].add(a)
                    queue.append(b)
        terminal_set = set(terminals)
        queue = deque(v for v in sorted(tree) if len(tree[v]) <= 1 and v not in terminal_set)
        while queue:
            vertex = queue.popleft()
            if vertex not in tree:
                continue
            for neighbor in tree.pop(vertex):
                tree[neighbor].remove(vertex)
                if len(tree[neighbor]) <= 1 and neighbor not in terminal_set:
                    queue.append(neighbor)
        return sorted(tree), [(a, b) for a in sorted(tree) for b in sorted(tree[a]) if a < b]

    def decode(self, nodes, edges, terminals) -> Route:
        positions = {
            vertex: (self.elapsed - 1 + vertex // self.size, vertex % self.size)
            for vertex in nodes
        }
        return Route(
            tuple(positions.values()),
            tuple((positions[a], positions[b]) for a, b in edges),
            tuple(positions[v] for v in terminals), self.elapsed,
        )

    def route_no_top(self, inst: Instruction) -> Route | None:
        terminals = []
        for target in inst.target_ids:
            positions = self.layout.factories if target == -1 else (self.layout.data_positions[target],)
            chosen = next((
                (self.elapsed - 1 + offset, pos)
                for pos in positions for offset in range(2)
                if not self.blocked[offset * self.size + pos]
            ), None)
            if chosen is None:
                return None
            terminals.append(chosen)
        return Route(tuple(terminals), (), tuple(terminals), self.elapsed)


def schedule_no_kink(
    instructions: Iterable[Instruction], *, layer_count: int = 2,
    magic_prep_time: int = 2, routing: str = "no-kink",
) -> ScheduleResult:
    """Schedule with finite factories; return routes in original instruction order."""
    if magic_prep_time < 0:
        raise ValueError("Magic preparation time must be nonnegative")
    if routing not in ("no-top", "no-kink"):
        raise ValueError(f"Unknown routing condition: {routing}")
    instructions = list(instructions)
    data_count = 1 + max((q for inst in instructions for q in inst.data_targets), default=-1)
    layout = Layout.naive_outer(data_count, layer_count)
    router = NoKinkRouter(layout, magic_prep_time)
    order, successors, in_degrees = prepare_look_ahead(instructions)
    ready = [i for i, degree in enumerate(in_degrees) if degree == 0]
    heapq.heapify(ready)
    routes = {}
    total_time = 0
    while len(routes) < len(instructions):
        deferred = []
        progressed = False
        while ready:
            index = heapq.heappop(ready)
            inst = instructions[order[index]]
            route = router.route(inst) if routing == "no-kink" else router.route_no_top(inst)
            if route is None:
                if not any(router.blocked):
                    raise RuntimeError(f"Routing failed on an idle chip: instruction {order[index]} {inst}")
                deferred.append(index)
                continue
            progressed = True
            for timing, pos in route.nodes:
                router.reserve(timing, pos)
                total_time = max(total_time, timing + 1)
            for timing, pos in route.terminals:
                if timing == router.elapsed:
                    router.reserve(timing - 1, pos)
            if inst.target_ids[0] == -1:
                timing, factory = route.terminals[0]
                router.occupy(factory, 1 + magic_prep_time + timing + 1 - router.elapsed)
            routes[order[index]] = route
            for successor in successors[index]:
                in_degrees[successor] -= 1
                if in_degrees[successor] == 0:
                    if successor > index:
                        heapq.heappush(ready, successor)
                    else:
                        deferred.append(successor)
        if not progressed and not deferred:
            raise RuntimeError("Instruction dependencies cannot make progress")
        ready = deferred
        heapq.heapify(ready)
        router.wait()
    return ScheduleResult(total_time, instructions, [routes[i] for i in range(len(instructions))], layout, magic_prep_time, routing)


def validate_schedule(result: ScheduleResult) -> None:
    """Independently check trees, endpoint rules, packing, dependencies, cooldown."""
    occupied = set()
    last_data: dict[int, int] = {}
    factory_uses: dict[int, list[int]] = {}
    layout = result.layout
    reserved = set(layout.data_positions) | set(layout.factories)
    total_time = 0
    for inst, route in zip(result.instructions, result.routes):
        nodes = set(route.nodes)
        if len(nodes) != len(route.nodes) or len(route.terminals) != len(inst.target_ids):
            raise ValueError("Duplicate route cells or incorrect terminal count")
        if not set(route.terminals) <= nodes:
            raise ValueError("Route omits a terminal")
        if occupied & nodes:
            raise ValueError("Routes overlap in space and time")
        occupied.update(nodes)
        for timing, pos in nodes:
            if not (route.window_end - 1 <= timing <= route.window_end and 0 <= pos < layout.chip_size):
                raise ValueError("Route leaves the two-slice chip")
            if pos in reserved and (timing, pos) not in route.terminals:
                raise ValueError("Route passes through an unrelated qubit or factory")
            total_time = max(total_time, timing + 1)
        for target, (timing, pos) in zip(inst.target_ids, route.terminals):
            if target == -1:
                if pos not in layout.factories:
                    raise ValueError("Magic terminal is not a factory")
                factory_uses.setdefault(pos, []).append(timing)
            else:
                if pos != layout.data_positions[target] or timing <= last_data.get(target, -1):
                    raise ValueError("Data operand or instruction dependency is incorrect")
                last_data[target] = timing
        if result.routing == "no-top":
            continue
        graph = {node: set() for node in nodes}
        if len(route.edges) != len(nodes) - 1:
            raise ValueError("Route is not a tree")
        for a, b in route.edges:
            if a not in nodes or b not in nodes or b in graph[a]:
                raise ValueError("Invalid or duplicate tree edge")
            if a[0] == b[0]:
                layout.direction(a[1], b[1])
            elif a[1] != b[1] or abs(a[0] - b[0]) != 1:
                raise ValueError("Invalid temporal edge")
            graph[a].add(b)
            graph[b].add(a)
        seen = {route.terminals[0]}
        queue = deque(seen)
        while queue:
            for neighbor in graph[queue.popleft()]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        if seen != nodes:
            raise ValueError("Route is disconnected")
        for index, terminal in enumerate(route.terminals):
            if len(graph[terminal]) != 1:
                raise ValueError("Terminal must be a leaf with one attachment")
            neighbor = next(iter(graph[terminal]))
            if neighbor[0] != terminal[0] or layout.direction(terminal[1], neighbor[1]) not in NoKinkRouter.directions(inst, index):
                raise ValueError("Invalid endpoint direction")
    for uses in factory_uses.values():
        uses.sort()
        if uses[0] < result.magic_prep_time or any(
            b - a < result.magic_prep_time + 1 for a, b in zip(uses, uses[1:])
        ):
            raise ValueError("Factory preparation/cooldown violated")
    if total_time != result.total_code_beats or len(result.routes) != len(result.instructions):
        raise ValueError("Incorrect total time or incomplete schedule")
