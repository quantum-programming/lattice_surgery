from __future__ import annotations

from pathlib import Path

from matplotlib import pyplot as plt
from qiskit import QuantumCircuit, qasm2
from qiskit.quantum_info import Operator

from common import ROOT, load_benchmark


BENCHMARKS = (
    "mqt_max_parallel",
    "mqt_min_parallel",
    "mqt_random_cnot_t",
)


def build_circuit(benchmark_path: Path) -> QuantumCircuit:
    benchmark = load_benchmark(benchmark_path)
    circuit = QuantumCircuit(benchmark["num_qubits"], name=benchmark["name"])
    for operation in benchmark["operations"]:
        if operation["gate"] == "cx":
            circuit.cx(operation["control"], operation["target"])
        elif operation["gate"] == "t":
            circuit.t(operation["target"])
        else:
            raise ValueError(f"Unsupported gate: {operation['gate']}")
    return circuit


def operation_signature(circuit: QuantumCircuit) -> list[tuple[str, tuple[int, ...]]]:
    return [
        (instruction.operation.name, tuple(circuit.find_bit(q).index for q in instruction.qubits))
        for instruction in circuit.data
    ]


def export_and_validate(benchmark_path: Path) -> Path:
    circuit = build_circuit(benchmark_path)
    qasm = qasm2.dumps(circuit)
    round_trip = qasm2.loads(qasm)
    if operation_signature(round_trip) != operation_signature(circuit):
        raise RuntimeError(f"Gate sequence changed during QASM conversion: {benchmark_path}")
    if not Operator(round_trip).equiv(Operator(circuit)):
        raise RuntimeError(f"Unitary changed during QASM conversion: {benchmark_path}")

    output = benchmark_path.with_suffix(".qasm")
    output.write_text(qasm, encoding="utf-8")
    return output


def export_visualization(benchmark_path: Path) -> Path:
    circuit = build_circuit(benchmark_path)
    output = ROOT / "figures" / f"{benchmark_path.stem}.png"
    output.parent.mkdir(exist_ok=True)
    figure = circuit.draw(output="mpl", fold=-1, scale=0.8)
    figure.suptitle(benchmark_path.stem.replace("_", " ").title())
    figure.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(figure)
    return output


def main() -> None:
    for name in BENCHMARKS:
        benchmark = ROOT / "benchmarks" / f"{name}.json"
        for path in (export_and_validate(benchmark), export_visualization(benchmark)):
            print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
