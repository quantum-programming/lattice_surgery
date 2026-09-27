"""Run the Resource Allocating Surface Code Compiler on one benchmark."""
from pathlib import Path
from typing import Any

from qiskit import qasm2  # type: ignore[import-untyped]


def run(benchmark: Path, height: int = 6, width: int = 6) -> dict[str, Any]:
    """Compile a CNOT circuit into a fixed-size QCB."""
    from surface_code_routing.compiled_qcb import compile_qcb  # type: ignore[import-untyped]
    from surface_code_routing.dag import DAG  # type: ignore[import-untyped]
    from surface_code_routing.instructions import CNOT  # type: ignore[import-untyped]

    circuit = qasm2.load(benchmark)
    dag = DAG(benchmark.stem)
    for instruction in circuit.data:
        if instruction.operation.name != "cx":
            raise ValueError("Surface Code Compiler adapter accepts only CNOTs")
        control, target = (circuit.find_bit(q).index for q in instruction.qubits)
        dag.add_gate(CNOT(f"q_{control}", f"q_{target}"))

    compiled = compile_qcb(dag, height, width)
    depth = int(compiled.n_cycles())
    active_volume = int(compiled.space_time_volume())
    return {
        "cycles": depth,
        "width": int(compiled.width),
        "height": int(compiled.height),
        "allocated_volume": int(compiled.width * compiled.height * depth),
        "active_space_time_volume": active_volume,
    }
