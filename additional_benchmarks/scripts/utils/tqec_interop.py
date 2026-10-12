"""Export the paper compiler's 2D CNOT schedules as TQEC block graphs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pyzx import EdgeType, VertexType
from pyzx.graph.graph_s import GraphS
from tqec.computation.block_graph import BlockGraph
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.synthesis.positioned import positioned_block_synthesis
from tqec.utils.position import Position3D


Coordinate = tuple[int, int, int]


def _axis(first: Position3D, second: Position3D) -> int:
    """Return the axis joining two neighboring positions."""
    if first.x != second.x:
        return 0
    if first.y != second.y:
        return 1
    return 2


def _corner_kind(direction_axes: frozenset[int], spider: int) -> tuple[int, int, int]:
    """Return a TQEC corner cube's X/Z walls, encoded as zero/one."""
    normal_axis = next(iter({0, 1, 2} - direction_axes))
    common_basis = 0 if spider == 0 else 1
    bases = [common_basis] * 3
    bases[normal_axis] = 1 - common_basis
    return tuple(bases)


def _solve_corner_types(
    graph: GraphS,
    positions: Mapping[int, Position3D],
    fixed_types: Mapping[int, VertexType],
) -> dict[int, int]:
    """Color degree-two bends so TQEC can join them without Hadamard pipes.

    Zero and one encode zero-phase Z and X spiders.  Either spider is an
    identity when inserted as a degree-two subdivision of a wire, so choosing
    these colors does not change the represented CNOT circuit.
    """

    def directions(vertex: int) -> frozenset[int]:
        return frozenset(
            _axis(positions[vertex], positions[neighbor])
            for neighbor in graph.neighbors(vertex)
        )

    direction_sets = {vertex: directions(vertex) for vertex in graph.vertices()}
    corners = {
        vertex
        for vertex in graph.vertices()
        if graph.type(vertex) != VertexType.BOUNDARY and len(direction_sets[vertex]) == 2
    }

    constraints: set[tuple[int, int, int]] = set()
    for start in corners:
        for neighbor in graph.neighbors(start):
            segment_axis = _axis(positions[start], positions[neighbor])
            previous, current = start, neighbor
            while current not in corners and graph.type(current) != VertexType.BOUNDARY:
                successors = [vertex for vertex in graph.neighbors(current) if vertex != previous]
                if len(successors) != 1:
                    raise ValueError("A routed wire branches away from a CNOT endpoint.")
                previous, current = current, successors[0]
                if _axis(positions[previous], positions[current]) != segment_axis:
                    raise ValueError("A route turns at a vertex not recognized as a corner.")
            if current in corners and start < current:
                constraints.add((start, current, segment_axis))

    assignments = {
        vertex: 0 if spider_type == VertexType.Z else 1
        for vertex, spider_type in fixed_types.items()
        if vertex in corners
    }
    variables = sorted(corners - assignments.keys())
    adjacency: dict[int, list[tuple[int, int]]] = {vertex: [] for vertex in corners}
    for first, second, segment_axis in constraints:
        adjacency[first].append((second, segment_axis))
        adjacency[second].append((first, segment_axis))

    def compatible(first: int, first_type: int, second: int, second_type: int, axis: int) -> bool:
        first_kind = _corner_kind(direction_sets[first], first_type)
        second_kind = _corner_kind(direction_sets[second], second_type)
        return all(first_kind[index] == second_kind[index] for index in range(3) if index != axis)

    def solve(index: int) -> bool:
        if index == len(variables):
            return True
        candidates = variables[index:]
        vertex = max(
            candidates,
            key=lambda item: sum(neighbor in assignments for neighbor, _ in adjacency[item]),
        )
        selected = variables.index(vertex, index)
        variables[index], variables[selected] = variables[selected], variables[index]
        for spider_type in (0, 1):
            if all(
                neighbor not in assignments
                or compatible(vertex, spider_type, neighbor, assignments[neighbor], axis)
                for neighbor, axis in adjacency[vertex]
            ):
                assignments[vertex] = spider_type
                if solve(index + 1):
                    return True
                del assignments[vertex]
        variables[index], variables[selected] = variables[selected], variables[index]
        return False

    if not solve(0):
        raise ValueError(
            "The schedule has no TQEC-compatible corner coloring without Hadamard pipes."
        )
    return assignments


def build_ours_positioned_zx(circuit: Any, schedule: Mapping[str, Any]) -> PositionedZX:
    """Embed one 2D, CNOT-only scheduler result as a positioned ZX graph."""
    if circuit.num_qubits != len(schedule["geometry"]["data"]):
        raise ValueError("The circuit and schedule have different numbers of data qubits.")

    operations: list[tuple[int, int]] = []
    for instruction in circuit.data:
        if instruction.operation.name != "cx":
            raise ValueError("The TQEC exporter currently accepts only CNOT instructions.")
        operations.append(tuple(circuit.find_bit(qubit).index for qubit in instruction.qubits))

    paths: list[list[Coordinate]] = [
        [tuple(int(value) for value in point) for point in path]
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
                VertexType.X if index == len(ordered_path) - 1 else VertexType.Z,
                fixed=index in (0, len(ordered_path) - 1),
            )
            for index, point in enumerate(ordered_path)
        ]
        for first, second in zip(path_vertices, path_vertices[1:]):
            graph.add_edge((first, second), EdgeType.SIMPLE)

    for corner, spider_type in _solve_corner_types(graph, positions, fixed_types).items():
        graph.set_type(corner, VertexType.Z if spider_type == 0 else VertexType.X)

    return PositionedZX(graph, positions)


def build_ours_block_graph(circuit: Any, schedule: Mapping[str, Any]) -> BlockGraph:
    """Convert one 2D, CNOT-only scheduler result into a TQEC block graph."""
    block_graph = positioned_block_synthesis(build_ours_positioned_zx(circuit, schedule))
    block_graph.name = "bounded_depth_schedule"
    block_graph.validate()
    return block_graph


def block_graph_metrics(block_graph: BlockGraph) -> dict[str, int | float | list[int]]:
    """Return representation-level TQEC metrics without physical lowering."""
    bounding_box = list(block_graph.bounding_box_size())
    return {
        "cubes": block_graph.num_cubes,
        "pipes": block_graph.num_pipes,
        "ports": block_graph.num_ports,
        "occupied_volume": block_graph.spacetime_volume,
        "bounding_box": bounding_box,
        "bounding_box_volume": bounding_box[0] * bounding_box[1] * bounding_box[2],
        "correlation_surfaces": len(block_graph.find_correlation_surfaces()),
    }
