"""Compile candidate seeded instances and summarize fully verified pairs."""
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from qiskit import qasm2  # type: ignore[import-untyped]

from qasm2in import qasm2in
from run_comparison import ROOT, check_circuit, get_commit_id, require_topols_patch, source_hash
from run_topols import run as run_topols  # pyright: ignore[reportImplicitRelativeImport]
from tqec_interop import build_ours_block_graph, export_verified_block_graph

SEEDS = tuple(range(41, 49))
FAMILIES = ("mqt_max_parallel", "mqt_min_parallel")


def _mean_sd(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "sample_sd": statistics.stdev(values),
        "min": min(values),
        "max": max(values),
    }


def _summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    passed = [row for row in rows if row["status"] == "passed"]
    complete_seeds = sorted({
        seed for seed in SEEDS
        if all(any(row["seed"] == seed and row["benchmark"] == family
                   and row["tool"] == tool for row in passed)
               for family in FAMILIES for tool in ("this_work", "topols"))
    })
    for family in FAMILIES:
        family_rows = [row for row in passed if row["benchmark"] == family
                       and row["seed"] in complete_seeds]
        for tool in ("this_work", "topols"):
            selected = [row for row in family_rows if row["tool"] == tool]
            summaries.append({
                "benchmark": family,
                "tool": tool,
                "n": len(selected),
                "tqec_occupied_volume": _mean_sd(
                    [row["tqec"]["occupied_volume"] for row in selected]),
                "tqec_time_extent": _mean_sd(
                    [row["tqec"]["bounding_box"][2] for row in selected]),
                "native_depth": _mean_sd([row["depth"] for row in selected]),
                "compilation_seconds": _mean_sd(
                    [row["compilation_seconds"] for row in selected]),
            })
        paired = {row["seed"]: row for row in family_rows if row["tool"] == "this_work"}
        topols_rows = [row for row in family_rows if row["tool"] == "topols"]
        reductions = [100 * (1 - paired[row["seed"]]["tqec"]["occupied_volume"]
                              / row["tqec"]["occupied_volume"])
                      for row in topols_rows]
        depth_reductions = [100 * (1 - paired[row["seed"]]["depth"] / row["depth"])
                            for row in topols_rows]
        z_reductions = [100 * (1 - paired[row["seed"]]["tqec"]["bounding_box"][2]
                                / row["tqec"]["bounding_box"][2])
                        for row in topols_rows]
        speedups = [row["compilation_seconds"]
                    / paired[row["seed"]]["compilation_seconds"]
                    for row in topols_rows]
        summaries.append({
            "benchmark": family, "tool": "paired_statistics",
            "n": len(reductions),
            "tqec_occupied_volume_reduction_percent": _mean_sd(reductions),
            "tqec_time_extent_reduction_percent": _mean_sd(z_reductions),
            "native_depth_reduction_percent": _mean_sd(depth_reductions),
            "compilation_speedup": _mean_sd(speedups),
        })
    return [{"complete_seeds": complete_seeds, "n": len(complete_seeds)}] + summaries


def main() -> None:
    if sys.platform != "linux":
        raise SystemExit("Run this comparison under WSL/Linux.")
    require_topols_patch()
    executable = ROOT / "work" / "ours_cnot"
    if not executable.is_file():
        raise FileNotFoundError("Compile work/ours_cnot as described in README.md")
    sweep = ROOT / "work" / "seed-sweep"
    inputs = sweep / "inputs"
    expected = {inputs / f"{family}-seed{seed}.qasm"
                for family in FAMILIES for seed in SEEDS}
    missing = expected - set(inputs.glob("*.qasm"))
    if missing:
        raise FileNotFoundError(
            "Generate sweep inputs first: " + ", ".join(sorted(str(path) for path in missing)))
    outputs = sweep / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    partial = ROOT / "seed_sweep.partial.json"
    base_report: dict[str, Any] = {
        "seeds": list(SEEDS),
        "variation": "MQT input-generation seed; compiler search seeds remain fixed",
        "commits": {
            "this_work": get_commit_id(ROOT.parent),
            "topols": get_commit_id(ROOT / "external" / "TopoLS"),
            "tqec": get_commit_id(ROOT / "external" / "tqec"),
        },
        "this_work_source_sha256": source_hash(),
        "configuration": {
            "this_work": "one layer; SA seed 1, 1,000,000 iterations; remove MSF and outer ring before scheduling; Double look-ahead; CareKinkParity",
            "topols": "three qubits per row (-l 3); Python engine; upstream defaults (block 10; ZX and direction optimization; seed 0; five internal seeds)",
        },
        "inputs": {},
        "rows": [],
    }
    if partial.exists():
        old = json.loads(partial.read_text())
        if old.get("commits") != base_report["commits"] or old.get(
                "this_work_source_sha256") != base_report["this_work_source_sha256"]:
            raise ValueError("The partial sweep was produced from different source revisions.")
        base_report["rows"] = [row for row in old["rows"] if row["seed"] in SEEDS]
        base_report["inputs"] = old["inputs"]
    report = base_report
    for family in FAMILIES:
        for seed in SEEDS:
            name = f"{family}-seed{seed}"
            qasm_path = inputs / f"{name}.qasm"
            circuit = check_circuit(qasm_path)
            report["inputs"][name] = hashlib.sha256(qasm_path.read_bytes()).hexdigest()
            native_input = outputs / f"{name}.in"
            native_input.write_text(qasm2in(circuit))
            started = time.perf_counter()
            if not any(row["benchmark"] == family and row["seed"] == seed
                       and row["tool"] == "this_work" for row in report["rows"]):
                completed = subprocess.run(
                    [str(executable), str(native_input)], capture_output=True,
                    text=True, check=True, timeout=300)
                wall_seconds = time.perf_counter() - started
                ours = json.loads(completed.stdout)
                geometry = ours.pop("geometry")
                graph = build_ours_block_graph(circuit, {
                    "width": ours["width"], "height": ours["height"],
                    "depth": ours["depth"], "geometry": geometry,
                })
                ours["tqec"] = export_verified_block_graph(
                    circuit, graph, outputs / f"ours-{name}.bgraph")
                ours.update({
                    "benchmark": family, "seed": seed, "tool": "this_work",
                    "compilation_seconds": wall_seconds,
                    "status": "passed",
                })
                report["rows"].append(ours)

            topols_output = outputs / f"topols-{name}"
            if not any(row["benchmark"] == family and row["seed"] == seed
                       and row["tool"] == "topols" for row in report["rows"]):
                if topols_output.exists():
                    shutil.rmtree(topols_output)
                try:
                    run_topols(qasm_path, topols_output,
                               bgraph_path=outputs / f"topols-{name}.bgraph")
                    topols = json.loads((topols_output / "metrics.json").read_text())
                    topols.update({
                        "benchmark": family, "seed": seed, "tool": "topols",
                        "status": "passed",
                    })
                except Exception as error:
                    if "same label" not in str(error):
                        raise
                    topols = {
                        "benchmark": family, "seed": seed, "tool": "topols",
                        "status": "failed_export", "error": str(error),
                    }
                report["rows"].append(topols)
            # Preserve completed cases if a later case fails.
            partial.write_text(
                json.dumps(report, indent=2) + "\n")

    summaries = _summaries(report["rows"])
    selection = summaries.pop(0)
    report["complete_seeds"] = selection["complete_seeds"]
    report["excluded_failures"] = [
        row for row in report["rows"] if row["status"] != "passed"]
    report["summaries"] = summaries
    destination = ROOT / "seed_sweep.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    partial.unlink(missing_ok=True)
    print(destination)


if __name__ == "__main__":
    main()
