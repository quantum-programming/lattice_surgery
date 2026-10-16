"""Regenerate the versioned seeded benchmark inputs and figure circuits."""
from pathlib import Path

from mqt.qecc.cococo.circuit_construction import (
    generate_max_parallel_circuit,
    generate_min_parallel_circuit,
)
from qiskit import QuantumCircuit  # type: ignore[import-untyped]

OUTPUT = Path(__file__).resolve().parent
FIGURES = OUTPUT.parent / "figures"
FIGURE_SEED = 45
SEEDS = tuple(range(41, 49))


def qasm_text(operations: list[tuple[int, int]]) -> str:
    # OpenQASM 2.0 specification: Sec. 2 / Table 1 for these declarations,
    # Sec. 3.1 for qelib1.inc and its lowercase cx gate (control, then target).
    # https://arxiv.org/pdf/1707.03429v2
    # OPENQASM declares the version; include loads gate definitions;
    # qreg q[8] declares eight qubits, indexed q[0] through q[7].
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[8];"]
    lines += [f"cx q[{control}],q[{target}];" for control, target in operations]
    return "\n".join(lines) + "\n"


def write_qasm(path: Path, operations: list[tuple[int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(qasm_text(operations), newline="\n")


def write_figure(name: str, operations: list[tuple[int, int]]) -> None:
    circuit = QuantumCircuit(8, name=name.replace("_", " ").title())
    for control, target in operations:
        circuit.cx(control, target)
    FIGURES.mkdir(exist_ok=True)
    # Qiskit generates Q-circuit code, including a standalone document wrapper.
    # Keep only its body so the manuscript owns the class and package imports.
    source = circuit.draw(output="latex_source")
    if not isinstance(source, str):
        raise TypeError("Qiskit latex_source output must be a string.")
    body = source.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    # Qiskit's renderer emits mixed space/tab indentation; normalize it so the
    # generated source passes Git's whitespace checks on every platform.
    body = body.replace("\t", "    ")
    (FIGURES / f"{name}.tex").write_text(body.strip() + "\n", newline="\n")


def write_circuit_seeds() -> None:
    """Write every statistical input and the selected manuscript circuits."""
    for seed in SEEDS:
        cases = {
            "mqt_max_parallel": generate_max_parallel_circuit(
                q=8, min_depth=32, seed=seed),
            "mqt_min_parallel": generate_min_parallel_circuit(
                q=8, min_depth=32, layer_size=2, seed=seed),
        }
        for family, operations in cases.items():
            write_qasm(OUTPUT / f"{family}-seed{seed}.qasm", operations)
            if seed == FIGURE_SEED:
                write_figure(family, operations)


if __name__ == "__main__":
    # Parallelism families and 4q gate counts: Herzog et al., Sec. VII.B / Fig. 10.
    # https://arxiv.org/html/2504.10591v2
    # For q=8, the max-parallel generator creates groups of four disjoint CXs.
    # layer_size=2 is our choice: the smallest group size above the serial case.
    # The min-parallel generator also enforces overlap between successive groups.
    # min_depth is a gate-count target here: 32 gives 8 groups of 4 or 16 of 2.
    write_circuit_seeds()
