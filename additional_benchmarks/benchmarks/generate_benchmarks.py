"""Regenerate the two fixed QASM inputs used in the comparison."""
from pathlib import Path

from mqt.qecc.cococo.circuit_construction import (
    generate_max_parallel_circuit,
    generate_min_parallel_circuit,
)
from qiskit import QuantumCircuit  # type: ignore[import-untyped]

OUTPUT = Path(__file__).resolve().parent
FIGURES = OUTPUT.parent / "figures"


def write(name: str, operations: list[tuple[int, int]]) -> None:
    # OpenQASM 2.0 specification: Sec. 2 / Table 1 for these declarations,
    # Sec. 3.1 for qelib1.inc and its lowercase cx gate (control, then target).
    # https://arxiv.org/pdf/1707.03429v2
    # OPENQASM declares the version; include loads gate definitions;
    # qreg q[9] declares nine qubits, indexed q[0] through q[8].
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[9];"]
    lines += [f"cx q[{control}],q[{target}];" for control, target in operations]
    text = "\n".join(lines) + "\n"
    path = OUTPUT / f"{name}.qasm"
    path.write_text(text, newline="\n")
    circuit = QuantumCircuit(9, name=name.replace("_", " ").title())
    for control, target in operations:
        circuit.cx(control, target)
    FIGURES.mkdir(exist_ok=True)
    # Qiskit generates Q-circuit code, including a standalone document wrapper.
    # Keep only its body so the manuscript owns the class and package imports.
    source = circuit.draw(output="latex_source")
    if not isinstance(source, str):
        raise TypeError("Qiskit latex_source output must be a string.")
    body = source.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    (FIGURES / f"{name}.tex").write_text(body.strip() + "\n", newline="\n")


if __name__ == "__main__":
    # Use the upstream default seed in both MQT QECC generators.
    # Parallelism families and 4q gate counts: Herzog et al., Sec. VII.B / Fig. 10.
    # https://arxiv.org/html/2504.10591v2
    # For q=9, the max-parallel generator creates groups of four disjoint CXs.
    # layer_size=2 is our choice: the smallest group size above the serial case.
    # The min-parallel generator also enforces overlap between successive groups.
    # min_depth is a gate-count target here: 36 gives 9 groups of 4 or 18 of 2.
    write("mqt_max_parallel", generate_max_parallel_circuit(q=9, min_depth=36))
    write("mqt_min_parallel", generate_min_parallel_circuit(
        q=9, min_depth=36, layer_size=2))
