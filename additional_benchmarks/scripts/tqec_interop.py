"""Synthesize, load, measure, and save the comparison BlockGraphs.

The semantic reconstruction of this work's schedules lives in schedule_to_zx;
TopoLS uses its own exporter.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tqec.computation.block_graph import BlockGraph
from tqec.interop.pyzx.synthesis.positioned import positioned_block_synthesis
from tqec.utils.position import Position3D

from cnot_semantics import verify_cnot_block_graph
from schedule_to_zx import build_ours_positioned_zx


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
    return _copy_with_port_labels(block_graph, labels)


def _copy_with_port_labels(
    block_graph: BlockGraph, labels: Mapping[Position3D, str],
) -> BlockGraph:
    """Copy a graph while assigning stable logical labels to every port.

    TQEC 8c352c0 provides BlockGraph.relabel_cubes(), but that method does not
    update the Cube objects retained by existing Pipe endpoints. Rebuilding the
    graph keeps its node and pipe objects consistent for BGRAPH serialization.
    """
    if set(labels) != set(block_graph.ports.values()):
        raise ValueError("The labels must identify every port exactly once.")
    result = BlockGraph(block_graph.name)
    for cube in block_graph.cubes:
        result.add_cube(cube.position, cube.kind, labels.get(cube.position, cube.label))
    for pipe in block_graph.pipes:
        result.add_pipe(pipe.u.position, pipe.v.position, pipe.kind)
    result.validate()
    return result


def build_topols_block_graph(compilation: Path) -> BlockGraph:
    """Use both parts of the pinned TopoLS's official TQEC export workflow.

    TopoLS's native .bgraph is a pickle, not TQEC's textual BGRAPH format.
    The metadata pickle is written beside the temporary native compilation.
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


def block_graph_metrics(block_graph: BlockGraph) -> dict[str, float | list[int]]:
    """Representation metrics using TQEC's official BlockGraph API.

    TQEC spacetime_volume counts ordinary cubes as 1, ports/pipes as 0, and
    Y half-cubes as 1/2. bounding_box_size includes ports.
    Source: external/tqec/src/tqec/computation/block_graph.py.
    """
    return {
        "occupied_volume": block_graph.spacetime_volume,
        "bounding_box": list(block_graph.bounding_box_size()),
    }


def export_verified_block_graph(
    circuit: Any, graph: BlockGraph, bgraph_path: Path,
) -> dict[str, Any]:
    """Verify and save BGRAPH at its final path.

    BGRAPH is TQEC's supported interchange format. The original graph must
    represent the input circuit, and the reloaded graph must be structurally
    equal to it.
    Source: tqec/docs/user_guide/bgraph.rst; block_graph.py from_bgraph/to_bgraph.
    """
    verify_cnot_block_graph(circuit, graph)
    metrics = block_graph_metrics(graph)
    bgraph_path.parent.mkdir(parents=True, exist_ok=True)
    graph.to_bgraph(bgraph_path, graph_name=circuit.name)
    reloaded = BlockGraph.from_bgraph(bgraph_path)
    if reloaded != graph:
        raise ValueError("BGRAPH roundtrip changed the BlockGraph.")
    return metrics
