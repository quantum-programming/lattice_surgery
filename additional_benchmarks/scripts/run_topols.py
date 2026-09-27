"""Run one TopoLS case and export only metrics and simple drawing geometry."""
import json
import os
import pickle
import runpy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: run_topols.py INPUT.qasm OUTPUT_DIRECTORY")
    source, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    name = source.stem
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark").mkdir()
    shutil.copy2(source, output / "benchmark" / source.name)

    import topols.pipeline as pipeline  # type: ignore[import-untyped]

    calls = []
    original = pipeline.zx_optimization

    def audited(graph, blocks):
        before = {"vertices": graph.num_vertices(), "edges": graph.num_edges()}
        result = original(graph, blocks)
        calls.append({"before": before, "after": {
            "vertices": graph.num_vertices(), "edges": graph.num_edges()}})
        return result

    pipeline.zx_optimization = audited
    program = ROOT / "external" / "TopoLS" / "docs" / "prog.py"
    sys.argv = [str(program), "-f", name, "-b", "10", "-zx", "1",
                "-dir", "1", "-l", "4", "-r", "0", "-s", "5",
                "-t", "3", "-i", "10000", "-csv", "metrics",
                "-sp", "0", "--engine", "python"]
    old_cwd = Path.cwd()
    try:
        os.chdir(output)
        runpy.run_path(str(program), run_name="__main__")
    finally:
        os.chdir(old_cwd)

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
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (output / "geometry.json").write_text(json.dumps(geometry) + "\n")


if __name__ == "__main__":
    main()
