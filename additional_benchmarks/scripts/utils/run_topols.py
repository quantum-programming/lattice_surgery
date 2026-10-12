"""Run one TopoLS case and export only metrics and simple drawing geometry."""
import json
import os
import pickle
import runpy
import shutil
import sys
from pathlib import Path

from qiskit import qasm2
from .tqec_interop import build_topols_block_graph, export_verified_block_graph

ROOT = Path(__file__).resolve().parents[2]


def run(source: Path, output: Path) -> None:
    source, output = source.resolve(), output.resolve()
    name = source.stem
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark").mkdir()
    shutil.copy2(source, output / "benchmark" / source.name)

    import topols.pipeline as pipeline  # type: ignore[import-untyped]

    calls = []
    original = pipeline.zx_optimization

    def audited(graph, blocks):
        # Observe upstream optimization without changing its inputs or result.
        before = {"vertices": graph.num_vertices(), "edges": graph.num_edges()}
        result = original(graph, blocks)
        calls.append({"before": before, "after": {
            "vertices": graph.num_vertices(), "edges": graph.num_edges()}})
        return result

    program = ROOT / "external" / "TopoLS" / "docs" / "prog.py"
    old_argv = sys.argv
    old_cwd = Path.cwd()
    try:
        pipeline.zx_optimization = audited
        # Use the supplied CLI, including its seed and search settings.
        # Source: external/TopoLS/docs/prog.py argument definitions.
        sys.argv = [str(program), "-f", name, "-b", "10", "-zx", "1",
                    "-dir", "1", "-l", "4", "-r", "0", "-s", "5",
                    "-t", "3", "-i", "10000", "-csv", "metrics",
                    "-sp", "0", "--engine", "python"]
        os.chdir(output)
        runpy.run_path(str(program), run_name="__main__")
    finally:
        os.chdir(old_cwd)
        sys.argv = old_argv
        pipeline.zx_optimization = original

    data = pickle.loads((output / "result" / "topols" / f"{name}.pkl").read_bytes())
    audit = calls[0]
    metrics = {
        "depth": int(data["time"]),
        "spatial_footprint": int(data["space"]),
        "bounding_box_volume": int(data["volume"]),
        "compilation_seconds": data["compilation_time"],
        "zx_graph": audit,
    }
    nodes = [{"position": list(position), "type": int(data["type_hist"][node])}
             for node, position in data["pos_hist"].items()]
    geometry = {"nodes": nodes,
                "paths": [[list(point) for point in path] for path in data["path_hist"]]}
    block_graph = build_topols_block_graph(output / "result" / "topols" / f"{name}.pkl")
    metrics["tqec"] = export_verified_block_graph(
        qasm2.load(source), block_graph, output / f"{name}.bgraph")
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (output / "geometry.json").write_text(json.dumps(geometry) + "\n")
