"""Minimal adapters for this work and the pinned TopoLS, restricted to 2D CNOTs.

Source links and the accounting boundary are documented in COMPARISON.md.
Only this work needs a geometric ZX reconstruction; TopoLS uses its own exporter.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pyzx as zx
from qiskit import qasm2

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
    """TQEC's _handle_corners rule, with X walls=0 and Z walls=1.

    A Z spider has a Z wall on the normal axis and X walls on the two route
    axes; an X spider has the opposite pattern. This describes the cube's
    walls, rather than assigning an X/Z label to each coordinate direction.
    Source: external/tqec/src/tqec/interop/pyzx/synthesis/positioned.py.
    """
    normal_axis = next(iter({0, 1, 2} - direction_axes))
    common_basis = 0 if spider == 0 else 1
    bases = [common_basis] * 3
    bases[normal_axis] = 1 - common_basis
    return bases[0], bases[1], bases[2]


def _solve_corner_types(
    graph: GraphS,
    positions: Mapping[int, Position3D],
    fixed_types: Mapping[int, VertexType],
) -> dict[int, int]:
    """Choose identity-spider colors so adjacent TQEC cube walls agree.

    Zero and one encode zero-phase Z and X spiders.  Either spider is an
    identity when inserted as a degree-two subdivision of a wire, so choosing
    these colors does not change the represented CNOT circuit.
    Branching CNOT spiders remain fixed. No Hadamard edges are introduced.
    Sources: TQEC's _handle_corners and _infer_cube_kind_from_pipe in
    interop/pyzx/synthesis/positioned.py; block_graph.py validate().
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

    # Straight degree-two sections inherit their wall orientation from their
    # ends. Each constraint below connects the corners at those two ends.
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

    def compatible(first: int, first_type: int, second: int, second_type: int,
                   axis: int) -> bool:
        first_kind = _corner_kind(direction_sets[first], first_type)
        second_kind = _corner_kind(direction_sets[second], second_type)
        # A pipe is open along its own axis; the other two wall bases must
        # agree. This is the non-Hadamard case of TQEC's pipe construction.
        return all(first_kind[index] == second_kind[index]
                   for index in range(3) if index != axis)

    for first, second, axis in constraints:
        if first in assignments and second in assignments and not compatible(
                first, assignments[first], second, assignments[second], axis):
            raise ValueError("Fixed spiders have incompatible TQEC walls.")

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
            "The graph has no TQEC-compatible corner coloring with its existing pipes."
        )
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

    operations: list[tuple[int, int]] = []
    for instruction in circuit.data:
        if instruction.operation.name != "cx":
            raise ValueError("The TQEC exporter currently accepts only CNOT instructions.")
        operations.append(tuple(circuit.find_bit(qubit).index for qubit in instruction.qubits))

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
    depth = int(schedule["depth"])
    labels = {}
    for qubit, point in enumerate(schedule["geometry"]["data"]):
        x, y = int(point[0]), int(point[1])
        labels[Position3D(x, y, -1)] = f"input_{qubit}"
        labels[Position3D(x, y, depth)] = f"output_{qubit}"
    return label_ports(block_graph, labels)


def label_ports(block_graph: BlockGraph, labels: Mapping[Position3D, str]) -> BlockGraph:
    """Copy a graph with explicit logical-qubit labels on every port."""
    if set(labels) != set(block_graph.ports.values()):
        raise ValueError("The labels must identify every port exactly once.")
    result = BlockGraph(block_graph.name)
    for cube in block_graph.cubes:
        result.add_cube(cube.position, cube.kind, labels.get(cube.position, cube.label))
    for pipe in block_graph.pipes:
        result.add_pipe(pipe.u.position, pipe.v.position, pipe.kind)
    result.validate()
    return result


def verify_cnot_block_graph(circuit: Any, block_graph: BlockGraph) -> None:
    """Verify a CNOT graph by reducing its comparison diagram to identity.

    Port order is logical-qubit order, not spatial order. This is a
    ZX-diagram equality check, not physical-circuit validation. Following PyZX's
    Circuit.verify_equality, we compose the exported graph with the adjoint of
    the expected circuit, run full_reduce, and require the exact identity wiring.
    This avoids constructing an exponentially large dense tensor. The reduction
    only modifies verification copies, never the exported geometry, and global
    scalar is ignored. Sources: TQEC PositionedZX.from_block_graph; PyZX
    Circuit.verify_equality and simplify.full_reduce.
    """
    if any(item.operation.name != "cx" for item in circuit.data):
        raise ValueError("ZX verification is limited to CNOT-only circuits.")
    block_graph.validate()
    positioned = PositionedZX.from_block_graph(block_graph)
    expected_labels = {f"{role}_{q}" for role in ("input", "output")
                       for q in range(circuit.num_qubits)}
    if set(block_graph.ports) != expected_labels:
        raise ValueError("The exported graph does not have the expected logical ports.")
    graph = positioned.g
    graph.set_inputs(tuple(positioned.p2v[block_graph.ports[f"input_{q}"]]
                           for q in range(circuit.num_qubits)))
    graph.set_outputs(tuple(positioned.p2v[block_graph.ports[f"output_{q}"]]
                            for q in range(circuit.num_qubits)))
    zx.full_reduce(graph)
    expected = zx.Circuit.from_qasm(qasm2.dumps(circuit))
    comparison = expected.to_graph().adjoint()
    comparison.compose(graph)
    zx.full_reduce(comparison)
    is_identity = (
        comparison.num_vertices() == 2 * circuit.num_qubits
        and all(comparison.edge_type(edge) == zx.EdgeType.SIMPLE
                for edge in comparison.edges())
        and all(comparison.connected(source, target)
                for source, target in zip(comparison.inputs(), comparison.outputs()))
    )
    if not is_identity:
        raise ValueError("The exported BlockGraph is not equivalent to the input CNOT circuit.")


def build_topols_block_graph(compilation: Path) -> BlockGraph:
    """Use both parts of the pinned TopoLS's official TQEC export workflow.

    TopoLS's native .bgraph is a pickle, not TQEC's textual BGRAPH format.
    The metadata pickle is kept beside the trusted local compilation in work/.
    No paths, colors, or port labels are reconstructed by our adapter.
    Sources: TopoLS export/bgraph.py build_pipe_diagram/save_bigraph;
    tools/pipe_sim.py load_block_graph (commit e564d35 plus the recorded
    temporary branching-endpoint patch).
    """
    from topols.export.bgraph import build_pipe_diagram, save_bigraph
    from topols.tools.pipe_sim import load_block_graph

    native_export = compilation.with_suffix(".topols.bgraph")
    nodes, edges = build_pipe_diagram(compilation)
    save_bigraph(native_export, nodes, edges)
    result = load_block_graph(native_export)
    result.validate()
    return result


def block_graph_metrics(block_graph: BlockGraph) -> dict[str, int | float | list[int]]:
    """Representation metrics using TQEC's official BlockGraph API.

    TQEC spacetime_volume counts ordinary cubes as 1, ports/pipes as 0, and
    Y half-cubes as 1/2. bounding_box_size includes ports. Its time extent
    is a coordinate range, not a calibrated execution duration.
    Source: external/tqec/src/tqec/computation/block_graph.py.
    """
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


def export_verified_block_graph(
    circuit: Any, graph: BlockGraph, bgraph_path: Path,
) -> dict[str, Any]:
    """Verify and save BGRAPH at its final path.

    BGRAPH is TQEC's official interchange format. Both original and reloaded
    graphs must represent the input circuit, and their accounting must agree.
    Source: tqec/docs/user_guide/bgraph.rst; block_graph.py from_bgraph/to_bgraph.
    """
    verify_cnot_block_graph(circuit, graph)
    metrics = block_graph_metrics(graph)
    bgraph_path.parent.mkdir(parents=True, exist_ok=True)
    graph.to_bgraph(bgraph_path, graph_name=circuit.name)
    reloaded = BlockGraph.from_bgraph(bgraph_path)
    verify_cnot_block_graph(circuit, reloaded)
    if block_graph_metrics(reloaded) != metrics:
        raise ValueError("BGRAPH roundtrip changed the representation metrics.")
    return {**metrics, "circuit_equivalent": True, "bgraph_roundtrip": True}
