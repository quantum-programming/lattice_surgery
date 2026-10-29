"""Compile candidate seeded instances and summarize fully verified pairs."""
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from comparison_common import (
    FAMILIES, ROOT, SEEDS, check_circuit, get_commit_id, source_hash,
)
from qasm2in import qasm2in
from run_topols import run as run_topols  # pyright: ignore[reportImplicitRelativeImport]
from tqec_interop import build_ours_block_graph, export_verified_block_graph

def main() -> None:
    if sys.platform != "linux":
        raise SystemExit("Run this comparison under WSL/Linux.")

    generator_python = ROOT / "benchmarks" / ".venv" / "bin" / "python"
    if not generator_python.is_file():
        raise FileNotFoundError("Run `uv sync --project benchmarks --frozen` first.")
    subprocess.run([
        str(generator_python), str(ROOT / "benchmarks" / "generate_benchmarks.py"),
    ], cwd=ROOT, check=True)
    inputs = ROOT / "benchmarks"
    expected = {inputs / f"{family}-seed{seed}.qasm"
                for family in FAMILIES for seed in SEEDS}
    missing = expected - set(inputs.glob("*.qasm"))
    if missing:
        raise FileNotFoundError(
            "Input generation failed: " + ", ".join(sorted(str(path) for path in missing)))

    outputs = ROOT / "results"
    outputs.mkdir(parents=True, exist_ok=True)
    partial = ROOT / "circuit_seeds.partial.json"
    base_report: dict[str, Any] = {
        "seeds": list(SEEDS),
        "variation": "MQT input-generation seed. Compiler search seeds remain fixed.",
        "commits": {
            "this_work": get_commit_id(ROOT.parent),
            "topols": get_commit_id(ROOT / "external" / "TopoLS"),
            "tqec": get_commit_id(ROOT / "external" / "tqec"),
        },
        "this_work_source_sha256": source_hash(),
        "configuration": {
            "this_work": "one layer, SA seed 1, 1,000,000 iterations, MSF and outer ring removed before scheduling, Double look-ahead, CareKinkParity",
            "topols": "three qubits per row (-l 3), Python engine, upstream defaults (block 10, ZX and direction optimization, seed 0, five internal seeds)",
        },
        "inputs": {},
        "rows": [],
    }
    if partial.exists():
        old = json.loads(partial.read_text())
        if old.get("commits") != base_report["commits"] or old.get(
                "this_work_source_sha256") != base_report["this_work_source_sha256"]:
            raise ValueError("The partial run was produced from different source revisions.")
        base_report["rows"] = [row for row in old["rows"] if row["seed"] in SEEDS]
        base_report["inputs"] = old["inputs"]

    report = base_report
    with tempfile.TemporaryDirectory(prefix="additional-benchmarks-") as temporary:
        temporary_path = Path(temporary)
        executable = temporary_path / "ours_cnot"
        subprocess.run([
            "g++", "-std=c++17", "-O2", "-D_GLIBCXX_ASSERTIONS",
            str(ROOT / "scripts" / "ours_cnot.cpp"), "-o", str(executable),
        ], cwd=ROOT, check=True)
        for family in FAMILIES:
            for seed in SEEDS:
                name = f"{family}-seed{seed}"
                qasm_path = inputs / f"{name}.qasm"
                circuit = check_circuit(qasm_path)
                report["inputs"][name] = hashlib.sha256(qasm_path.read_bytes()).hexdigest()
                native_input = temporary_path / f"{name}.in"
                native_input.write_text(qasm2in(circuit))
                if not any(row["benchmark"] == family and row["seed"] == seed
                           and row["tool"] == "this_work" for row in report["rows"]):
                    started = time.perf_counter()
                    completed = subprocess.run(
                        [str(executable), str(native_input)], capture_output=True,
                        text=True, check=True, timeout=300)
                    wall_seconds = time.perf_counter() - started
                    ours = json.loads(completed.stdout)
                    geometry = ours.pop("geometry")
                    graph = build_ours_block_graph(circuit, {
                        "depth": ours["total_execution_time"], "geometry": geometry,
                    })
                    ours["tqec"] = export_verified_block_graph(
                        circuit, graph, outputs / f"ours-{name}.bgraph")
                    ours.update({
                        "benchmark": family, "seed": seed, "tool": "this_work",
                        "compilation_seconds": wall_seconds,
                        "status": "passed",
                    })
                    report["rows"].append(ours)

                if not any(row["benchmark"] == family and row["seed"] == seed
                           and row["tool"] == "topols" for row in report["rows"]):
                    topols_output = temporary_path / f"topols-{name}"
                    bgraph_path = outputs / f"topols-{name}.bgraph"
                    run_topols(qasm_path, topols_output, bgraph_path=bgraph_path)
                    topols = json.loads((topols_output / "metrics.json").read_text())
                    topols.update({
                        "benchmark": family, "seed": seed, "tool": "topols",
                        "status": "passed",
                    })
                    report["rows"].append(topols)
                # Preserve completed cases if a later case fails.
                partial.write_text(json.dumps(report, indent=2) + "\n")

    destination = ROOT / "circuit_seeds.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    partial.unlink(missing_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze_circuit_seeds.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "render_figures.py")],
                   cwd=ROOT, check=True)
    print(destination, flush=True)


if __name__ == "__main__":
    main()
