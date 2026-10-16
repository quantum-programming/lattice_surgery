"""Run one TopoLS case and export metrics and the verified TQEC representation."""
import json
import pickle
import shutil
import subprocess
import sys
from pathlib import Path

from qiskit import qasm2
from tqec_interop import build_topols_block_graph, export_verified_block_graph

ROOT = Path(__file__).resolve().parents[1]


def run(source: Path, output: Path, bgraph_path: Path) -> None:
    source, output = source.resolve(), output.resolve()
    name = source.stem
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark").mkdir()
    shutil.copy2(source, output / "benchmark" / source.name)

    program = ROOT / "external" / "TopoLS" / "docs" / "prog.py"
    # Use TopoLS's supplied CLI and its documented defaults. Only the common
    # 7x7 footprint and the reference Python engine are selected explicitly.
    subprocess.run([
        sys.executable, str(program), "-f", name, "-l", "3", "--engine", "python",
    ], cwd=output, check=True)

    data = pickle.loads((output / "result" / "topols" / f"{name}.pkl").read_bytes())
    metrics = {
        "total_execution_time": int(data["time"]),
        "spatial_footprint": int(data["space"]),
        "compilation_seconds": data["compilation_time"],
    }
    block_graph = build_topols_block_graph(output / "result" / "topols" / f"{name}.pkl")
    circuit = qasm2.load(source)
    circuit.name = source.stem
    metrics["tqec"] = export_verified_block_graph(circuit, block_graph, bgraph_path)
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
