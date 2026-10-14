"""Convert a CNOT-only OpenQASM 2 circuit to the native Problem input format.

Usage: python scripts/qasm2in.py input.qasm output.in
Requires Qiskit. No fixed qubit count or gate count is imposed.
"""
from pathlib import Path
import sys

from qiskit import QuantumCircuit, qasm2  # type: ignore[import-untyped]


def qasm2in(circuit: QuantumCircuit) -> str:
    """Return native CX instructions in their original order.

    Problem::read_file in src/cpp/util/problem.hpp accepts CX control target
    and infers the qubit count from contiguous, used indices starting at zero.
    Unsupported operations and unused qubits are rejected, not discarded.
    """
    lines = []
    used: set[int] = set()
    for instruction in circuit.data:
        if instruction.operation.name != "cx":
            raise ValueError("This converter supports CNOT-only circuits.")
        control, target = (circuit.find_bit(q).index for q in instruction.qubits)
        lines.append(f"CX {control} {target}\n")
        used.update((control, target))
    if not lines or used != set(range(circuit.num_qubits)):
        raise ValueError("Native input requires a nonempty circuit using every declared qubit.")
    return "".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/qasm2in.py input.qasm output.in")
    text = qasm2in(qasm2.load(Path(sys.argv[1])))
    Path(sys.argv[2]).write_text(text)
