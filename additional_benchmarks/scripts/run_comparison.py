"""Reproduce the fixed two-circuit comparison used for Reviewer 1."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from qiskit import qasm2  # type: ignore[import-untyped]

from qasm2in import qasm2in
from run_topols import run as run_topols  # pyright: ignore[reportImplicitRelativeImport]
from tqec_interop import build_ours_block_graph, export_verified_block_graph

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ("mqt_max_parallel", "mqt_min_parallel")


def get_commit_id(path: Path) -> str:
    """Return the HEAD commit ID of a Git repository."""
    # path: repository directory; for a submodule, this records its own HEAD.
    # git -c safe.directory=...: trust this directory for this invocation only.
    # -C path: run Git in this directory, independently of Python's working directory.
    # rev-parse HEAD: resolve the currently checked-out commit to its full ID.
    result = subprocess.run(["git", "-c", f"safe.directory={path.as_posix()}",
                             "-C", str(path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def check_circuit(path: Path):
    """Load a benchmark and verify its fixed size and gate set."""
    circuit = qasm2.load(path)
    if circuit.num_qubits != 9 or circuit.size() != 36 or set(circuit.count_ops()) != {"cx"}:
        raise ValueError(f"Expected a nine-qubit, 36-CNOT circuit: {path}")
    return circuit


def source_hash() -> str:
    """Hash the C++ headers used by the native comparison."""
    digest = hashlib.sha256()
    for path in sorted((ROOT.parent / "src" / "cpp").rglob("*.hpp")):
        digest.update(path.relative_to(ROOT.parent).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    """Run the current two-tool comparison on the saved QASM inputs."""
    if sys.platform != "linux":
        raise SystemExit("Run this comparison under WSL/Linux.")
    executable = ROOT / "work" / "ours_cnot"
    if not executable.is_file():
        raise FileNotFoundError("Compile work/ours_cnot as described in COMPARISON.md")
    work = ROOT / "work" / "tqec-comparison"
    # Replace only this run's artifacts, preserving all other work/ contents.
    # Reject redirected paths before recursive deletion.
    if work.resolve() != ROOT.resolve() / "work" / "tqec-comparison":
        raise ValueError("The fixed output directory must not be redirected.")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    report: dict[str, Any] = {
        "inputs": {},
        "commits": {"this_work": get_commit_id(ROOT.parent),
                    "topols": get_commit_id(ROOT / "external" / "TopoLS"),
                    "tqec": get_commit_id(ROOT / "external" / "tqec")},
        "this_work_source_sha256": source_hash(),
        "configuration": {
            "this_work": "one layer; SA seed 1, 1,000,000 iterations; remove MSF and outer ring before scheduling; Double look-ahead; CareKinkParity",
            "topols": "three qubits per row (-l 3); Python engine; remaining search settings use upstream defaults (block 10; ZX and direction optimization enabled; seed 0; five internal seeds)",
        },
        "rows": [],  # One result per benchmark and compiler (four in total).
    }
    for name in BENCHMARKS:
        qasm_path = ROOT / "benchmarks" / f"{name}.qasm"
        circuit = check_circuit(qasm_path)
        report["inputs"][name] = hashlib.sha256(qasm_path.read_bytes()).hexdigest()
        native_input = work / f"{name}.in"
        native_input.write_text(qasm2in(circuit))

        completed = subprocess.run([str(executable), str(native_input)], capture_output=True,
                                   text=True, check=True, timeout=300)
        ours = json.loads(completed.stdout)
        geometry = ours.pop("geometry")
        schedule = {"width": ours["width"], "height": ours["height"],
                    "depth": ours["depth"], "geometry": geometry}
        block_graph = build_ours_block_graph(circuit, schedule)
        tqec_metrics = export_verified_block_graph(
            circuit, block_graph,
            bgraph_path=ROOT / "results" / f"ours-{name}.bgraph")
        if tqec_metrics["occupied_volume"] != ours["occupied_volume"]:
            raise ValueError("TQEC and the native scheduler disagree on occupied volume.")
        (work / f"ours-{name}.json").write_text(json.dumps(schedule, indent=2) + "\n")
        ours.update({
            "tqec": tqec_metrics,
            "tool": "this_work", "benchmark": name, "status": "passed",
            "depth_unit": "code beat",
            "allocated_volume": ours["allocated_sites"] * ours["depth"],
            "active_data_density": ours["active_data"] / ours["allocated_sites"],
            "finite_data_slot_density": ours["data_slots"] / ours["allocated_sites"],
            "asymptotic_data_slot_density": 0.25,
        })
        report["rows"].append(ours)

        output = work / f"topols-{name}"
        run_topols(qasm_path, output,
                   bgraph_path=ROOT / "results" / f"topols-{name}.bgraph")
        topols = json.loads((output / "metrics.json").read_text())
        topols.update({"tool": "topols", "benchmark": name, "status": "passed",
                       "depth_unit": "pipe-diagram time coordinate", "storage_density": None})
        report["rows"].append(topols)

    results = ROOT / "comparison.json"
    results.write_text(json.dumps(report, indent=2) + "\n")
    print(results)


if __name__ == "__main__":
    main()
