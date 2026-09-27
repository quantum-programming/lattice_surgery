"""Reproduce the fixed two-circuit comparison used for Reviewer 1."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from qiskit import qasm2  # type: ignore[import-untyped]

from render_structures import render  # pyright: ignore[reportImplicitRelativeImport]
from run_topols import run as run_topols  # pyright: ignore[reportImplicitRelativeImport]

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ("mqt_max_parallel", "mqt_min_parallel")


def get_commit_id(path: Path) -> str:
    """Return the HEAD commit ID of a Git repository."""
    result = subprocess.run(["git", "-c", f"safe.directory={path.as_posix()}",
                             "-C", str(path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def check_circuit(path: Path):
    """Load a benchmark and verify its fixed size and gate set."""
    circuit = qasm2.load(path)
    if circuit.num_qubits != 6 or circuit.size() != 24 or set(circuit.count_ops()) != {"cx"}:
        raise ValueError(f"Expected a six-qubit, 24-CNOT circuit: {path}")
    return circuit


def source_hash() -> str:
    """Hash the C++ headers used by the native comparison."""
    digest = hashlib.sha256()
    for path in sorted((ROOT.parent / "src" / "cpp").rglob("*.hpp")):
        digest.update(path.relative_to(ROOT.parent).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    """Run both compilers, collect metrics, and render the comparison."""
    if sys.platform != "linux":
        raise SystemExit("Run this comparison under WSL/Linux.")
    executable = ROOT / "work" / "ours_cnot"
    if not executable.is_file():
        raise FileNotFoundError("Compile work/ours_cnot as described in COMPARISON.md")
    work = ROOT / "work" / "comparison"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    report: dict[str, Any] = {
        "inputs": {},
        "commits": {"this_work": get_commit_id(ROOT.parent),
                    "topols": get_commit_id(ROOT / "external" / "TopoLS"),
                    "mqt_qecc": get_commit_id(ROOT / "external" / "mqt_qecc")},
        "this_work_source_sha256": source_hash(),
        "configuration": {
            "this_work": "one layer; outer factories; SA seed 1, 1,000,000 iterations; Double look-ahead; CareKinkParity",
            "topols": "block 10; ZX and direction optimization enabled; Python engine; seed 0; five internal seeds",
        },
        "rows": [],
    }
    geometries = {}
    for name in BENCHMARKS:
        qasm_path = ROOT / "benchmarks" / f"{name}.qasm"
        circuit = check_circuit(qasm_path)
        report["inputs"][name] = hashlib.sha256(qasm_path.read_bytes()).hexdigest()
        native_input = work / f"{name}.in"
        operations = []
        for instruction in circuit.data:
            control, target = (circuit.find_bit(q).index for q in instruction.qubits)
            operations.append(f"CX {control} {target}\n")
        native_input.write_text("".join(operations))

        completed = subprocess.run([str(executable), str(native_input)], capture_output=True,
                                   text=True, check=True, timeout=300)
        ours = json.loads(completed.stdout)
        geometry = ours.pop("geometry")
        ours.update({
            "tool": "this_work", "benchmark": name, "status": "passed",
            "depth_unit": "code beat",
            "allocated_volume": ours["allocated_sites"] * ours["depth"],
            "active_data_density": ours["active_data"] / ours["allocated_sites"],
            "finite_data_slot_density": ours["data_slots"] / ours["allocated_sites"],
            "asymptotic_data_slot_density": 0.25,
        })
        report["rows"].append(ours)
        geometries[("ours", name)] = {"depth": ours["depth"], "geometry": geometry}

        output = work / f"topols-{name}"
        run_topols(qasm_path, output)
        topols = json.loads((output / "metrics.json").read_text())
        topols.update({"tool": "topols", "benchmark": name, "status": "passed",
                       "depth_unit": "pipe-diagram time coordinate", "storage_density": None})
        report["rows"].append(topols)
        geometries[("topols", name)] = json.loads((output / "geometry.json").read_text())

    results = ROOT / "comparison.json"
    results.write_text(json.dumps(report, indent=2) + "\n")
    name = "mqt_min_parallel"
    ours_geometry = work / f"ours-{name}.json"
    topols_geometry = work / f"topols-{name}.json"
    ours_geometry.write_text(json.dumps(geometries[("ours", name)]))
    topols_geometry.write_text(json.dumps(geometries[("topols", name)]))
    render(ours_geometry, topols_geometry, ROOT / "figures" / "structure_comparison.png")
    print(results)


if __name__ == "__main__":
    main()
