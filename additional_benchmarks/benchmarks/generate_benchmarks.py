"""Regenerate the two fixed QASM inputs used in the comparison."""
import argparse
from pathlib import Path

from mqt.qecc.cococo.circuit_construction import (
    generate_max_parallel_circuit,
    generate_min_parallel_circuit,
)
from qiskit import QuantumCircuit  # type: ignore[import-untyped]

OUTPUT = Path(__file__).resolve().parent
FIGURES = OUTPUT.parent / "figures"


def write(name: str, operations: list[tuple[int, int]], *, check: bool = False) -> None:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[6];"]
    lines += [f"cx q[{control}],q[{target}];" for control, target in operations]
    text = "\n".join(lines) + "\n"
    path = OUTPUT / f"{name}.qasm"
    if check:
        if path.read_text() != text:
            raise ValueError(f"The MQT generator does not reproduce {path.name}.")
        print(f"{path.name}: matches mqt-qecc 2.0.0")
        return
    path.write_text(text, newline="\n")
    circuit = QuantumCircuit(6, name=name.replace("_", " ").title())
    for control, target in operations:
        circuit.cx(control, target)
    circuit.draw(output="mpl", filename=str(FIGURES / f"{name}.png"), fold=-1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify QASM without overwriting files")
    args = parser.parse_args()
    write("mqt_max_parallel", generate_max_parallel_circuit(q=6, min_depth=24, seed=45),
          check=args.check)
    write("mqt_min_parallel", generate_min_parallel_circuit(
        q=6, min_depth=24, layer_size=2, seed=45), check=args.check)
