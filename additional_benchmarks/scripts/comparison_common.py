"""Shared configuration and validation for the TopoLS comparison."""
import hashlib
import subprocess
from pathlib import Path

from qiskit import qasm2  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ("mqt_max_parallel", "mqt_min_parallel")
SEEDS = tuple(range(41, 49))
FIGURE_SEED = 45


def get_commit_id(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path),
         "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def check_circuit(path: Path):
    circuit = qasm2.load(path)
    circuit.name = path.stem
    if circuit.num_qubits != 8 or circuit.size() != 32 or set(circuit.count_ops()) != {"cx"}:
        raise ValueError(f"Expected an eight-qubit, 32-CNOT circuit: {path}")
    used = {circuit.find_bit(qubit).index
            for instruction in circuit.data for qubit in instruction.qubits}
    if used != set(range(8)):
        raise ValueError(f"Expected all eight qubits to be used: {path}")
    return circuit


def source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT.parent / "src" / "cpp").rglob("*.hpp")):
        digest.update(path.relative_to(ROOT.parent).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()
