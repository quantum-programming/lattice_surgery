"""Translate this work's CNOT schedules into positioned ZX graphs.

References:
- https://zxcalculus.com/intro.html
- https://arxiv.org/pdf/2012.13966
- https://tqec.github.io/tqec/user_guide/terminology.html
"""

from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any

from pyzx import EdgeType, VertexType
from pyzx.graph.graph_s import GraphS
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.utils.enums import Basis
from tqec.utils.position import Direction3D, Position3D

from cnot_semantics import cnot_operations


Coordinate = tuple[int, int, int]
SPIDER_TYPES = (VertexType.Z, VertexType.X)
SAME_SPIDER_PAIRS = {(VertexType.Z, VertexType.Z), (VertexType.X, VertexType.X)}
OPPOSITE_SPIDER_PAIRS = {(VertexType.Z, VertexType.X), (VertexType.X, VertexType.Z)}
ALL_DIRECTIONS = frozenset(Direction3D.all_directions())


def _direction(first: Position3D, second: Position3D) -> Direction3D:
    """Return the axis direction joining two neighboring positions."""
    return Direction3D.from_neighbouring_positions(first, second)


def _corner_kind(
    route_directions: frozenset[Direction3D], spider: VertexType,
) -> tuple[Basis, Basis, Basis]:
    """Mirror the corner convention of TQEC's positioned synthesis.

    For a vertex with edges along exactly two coordinate axes, the pinned
    ``_handle_corners`` implementation assigns the spider basis to the unused
    axis and the opposite basis to the other two axes. This is a convention of
    that synthesis algorithm, not a general rule derived from the definition
    of a TQEC cube. We reproduce it here only to predict which corner cubes the
    official synthesis will construct.

    Source: external/tqec/src/tqec/interop/pyzx/synthesis/positioned.py,
    ``_handle_corners`` (TQEC commit 8c352c0).
    """
    if spider not in SPIDER_TYPES:
        raise ValueError("A corner must be a zero-phase Z or X spider.")
    if len(route_directions) != 2:
        raise ValueError("A corner must use exactly two coordinate directions.")
    normal_direction = next(iter(ALL_DIRECTIONS - route_directions))
    normal_basis = Basis.Z if spider == VertexType.Z else Basis.X
    bases = [normal_basis.flipped()] * 3
    bases[normal_direction.value] = normal_basis
    return bases[0], bases[1], bases[2]


def _opposite_spider(spider: VertexType) -> VertexType:
    if spider == VertexType.Z:
        return VertexType.X
    if spider == VertexType.X:
        return VertexType.Z
    raise ValueError("Only Z and X spiders can be flipped.")


def _solve_corner_types(
    graph: GraphS,
    positions: Mapping[int, Position3D],
    fixed_types: Mapping[int, VertexType],
) -> dict[int, VertexType]:
    """Choose identity-spider colors so adjacent TQEC cube walls agree.

    Either zero-phase Z or X spider is an identity when inserted as a
    degree-two subdivision of a wire, so choosing these colors does not change
    the represented CNOT circuit.
    Branching CNOT spiders remain fixed. Each straight segment constrains the
    types at its corner endpoints to be equal or opposite, so the assignments
    are obtained by propagating binary parity constraints. No Hadamard edges
    are introduced.

    TQEC's positioned synthesis fixes each corner cube from its spider type
    before inferring the remaining pipes. Without a consistent assignment, it
    reports conflicting cube kinds for the routed CNOT geometries.
    Sources: TQEC's _handle_corners and _infer_cube_kind_from_pipe in
    interop/pyzx/synthesis/positioned.py; block_graph.py validate().
    """

    def directions(vertex: int) -> frozenset[Direction3D]:
        return frozenset(
            _direction(positions[vertex], positions[neighbor])
            for neighbor in graph.neighbors(vertex)
        )

    direction_sets = {vertex: directions(vertex) for vertex in graph.vertices()}
    corners = {
        vertex
        for vertex in graph.vertices()
        if graph.type(vertex) != VertexType.BOUNDARY and len(direction_sets[vertex]) == 2
    }

    # Straight degree-two sections inherit their wall orientation from their
    # ends. Each constraint below connects the corners at those two ends.
    constraints: set[tuple[int, int, Direction3D]] = set()
    for start in corners:
        for neighbor in graph.neighbors(start):
            segment_direction = _direction(positions[start], positions[neighbor])
            previous, current = start, neighbor
            while current not in corners and graph.type(current) != VertexType.BOUNDARY:
                successors = [vertex for vertex in graph.neighbors(current) if vertex != previous]
                if len(successors) != 1:
                    raise ValueError("A routed wire branches away from a CNOT endpoint.")
                previous, current = current, successors[0]
                if _direction(positions[previous], positions[current]) != segment_direction:
                    raise ValueError("A route turns at a vertex not recognized as a corner.")
            if current in corners and start < current:
                constraints.add((start, current, segment_direction))

    assignments: dict[int, VertexType] = {
        vertex: spider_type
        for vertex, spider_type in fixed_types.items()
        if vertex in corners
    }
    adjacency: dict[int, list[tuple[int, bool]]] = {vertex: [] for vertex in corners}
    for first, second, segment_direction in constraints:
        compatible = set()
        for first_type in SPIDER_TYPES:
            first_kind = _corner_kind(direction_sets[first], first_type)
            for second_type in SPIDER_TYPES:
                second_kind = _corner_kind(direction_sets[second], second_type)
                if all(
                    first_kind[direction.value] == second_kind[direction.value]
                    for direction in ALL_DIRECTIONS
                    if direction != segment_direction
                ):
                    compatible.add((first_type, second_type))
        if compatible == SAME_SPIDER_PAIRS:
            requires_flip = False
        elif compatible == OPPOSITE_SPIDER_PAIRS:
            requires_flip = True
        else:
            raise ValueError(
                "A corner pair is not a binary positioned-synthesis constraint."
            )
        adjacency[first].append((second, requires_flip))
        adjacency[second].append((first, requires_flip))

    pending = deque(assignments)

    def propagate() -> None:
        while pending:
            vertex = pending.popleft()
            for neighbor, requires_flip in adjacency[vertex]:
                required = (
                    _opposite_spider(assignments[vertex])
                    if requires_flip else assignments[vertex]
                )
                if neighbor in assignments:
                    if assignments[neighbor] != required:
                        raise ValueError(
                            "The graph has incompatible TQEC corner constraints."
                        )
                    continue
                assignments[neighbor] = required
                pending.append(neighbor)

    propagate()
    for vertex in sorted(corners):
        if vertex not in assignments:
            assignments[vertex] = VertexType.Z
            pending.append(vertex)
            propagate()
    return assignments


def build_ours_positioned_zx(circuit: Any, schedule: Mapping[str, Any]) -> PositionedZX:
    """Keep the scheduler's coordinates and embed each CNOT as Z--X.

    Data are persistent pillars. CX control/target are the Z/X branching
    spiders; internal route points are zero-phase degree-two identities.
    See PyZX's CNOT.to_graph and scripts/ours_cnot.cpp for the two
    input contracts. Full-circuit ZX identity reduction checks this reconstruction.
    """
    if circuit.num_qubits != len(schedule["geometry"]["data"]):
        raise ValueError("The circuit and schedule have different numbers of data qubits.")

    operations = cnot_operations(circuit)

    paths: list[list[Coordinate]] = [
        [(int(point[0]), int(point[1]), int(point[2])) for point in path]
        for path in schedule["geometry"]["paths"]
    ]
    if len(paths) != len(operations):
        raise ValueError("The schedule must contain one path per CNOT instruction.")

    data_positions = [
        (int(point[0]), int(point[1])) for point in schedule["geometry"]["data"]
    ]
    depth = int(schedule["depth"])
    graph = GraphS()
    positions: dict[int, Position3D] = {}
    vertices_by_position: dict[Coordinate, int] = {}
    fixed_types: dict[int, VertexType] = {}

    def vertex(
        position: Coordinate,
        spider_type: VertexType = VertexType.Z,
        *,
        fixed: bool = False,
    ) -> int:
        if position in vertices_by_position:
            existing = vertices_by_position[position]
            if fixed:
                if existing in fixed_types and fixed_types[existing] != spider_type:
                    raise ValueError(f"Conflicting CNOT roles at {position}.")
                fixed_types[existing] = spider_type
                graph.set_type(existing, spider_type)
            return existing
        created = graph.add_vertex(spider_type)
        vertices_by_position[position] = created
        positions[created] = Position3D(*position)
        if fixed:
            fixed_types[created] = spider_type
        return created

    inputs: list[int] = []
    outputs: list[int] = []
    for x, y in data_positions:
        # Native occupied storage runs at t=0..depth-1. The two extra boundary
        # vertices expose the logical inputs/outputs and have zero TQEC volume.
        input_vertex = vertex((x, y, -1), VertexType.BOUNDARY, fixed=True)
        inputs.append(input_vertex)
        previous = input_vertex
        for time in range(depth):
            current = vertex((x, y, time))
            graph.add_edge((previous, current), EdgeType.SIMPLE)
            previous = current
        output_vertex = vertex((x, y, depth), VertexType.BOUNDARY, fixed=True)
        outputs.append(output_vertex)
        graph.add_edge((previous, output_vertex), EdgeType.SIMPLE)
    graph.set_inputs(tuple(inputs))
    graph.set_outputs(tuple(outputs))

    for (control, target), path in zip(operations, paths, strict=True):
        # The scheduler stores surgery_paths[inst.instId], even after dependency
        # reordering: doubleTimeSlice.hpp look_ahead_schedule(). Path direction
        # need not be control-to-target, so identify it by its data endpoints.
        expected_endpoints = {data_positions[control], data_positions[target]}
        actual_endpoints = {path[0][:2], path[-1][:2]}
        if actual_endpoints != expected_endpoints:
            raise ValueError(
                f"Path endpoints {actual_endpoints} do not match CNOT operands "
                f"{expected_endpoints}."
            )
        ordered_path: Sequence[Coordinate]
        ordered_path = path if path[0][:2] == data_positions[control] else tuple(reversed(path))
        path_vertices = [
            vertex(
                point,
                # The first and last vertices are the CNOT control and target, which must be Z and X spiders, respectively.
                # https://arxiv.org/pdf/2012.13966 (eq. (1))
                # https://arxiv.org/pdf/2606.21192 (Table IV)
                VertexType.X if index == len(ordered_path) - 1 else VertexType.Z,
                fixed=index in (0, len(ordered_path) - 1),
            )
            for index, point in enumerate(ordered_path)
        ]
        for first, second in zip(path_vertices, path_vertices[1:]):
            graph.add_edge((first, second), EdgeType.SIMPLE)

    for corner, spider_type in _solve_corner_types(graph, positions, fixed_types).items():
        graph.set_type(corner, spider_type)

    return PositionedZX(graph, positions)

