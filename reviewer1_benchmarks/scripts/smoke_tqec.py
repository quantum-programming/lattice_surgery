from __future__ import annotations

import time

from common import emit_result
from tqec import Basis, NoiseModel, compile_block_graph
from tqec.gallery.cnot import cnot


def main() -> None:
    block_graph = cnot(Basis.Z)
    observables = block_graph.find_correlation_surfaces()
    started = time.perf_counter()
    compiled = compile_block_graph(block_graph, observables=[observables[0]])
    circuit = compiled.generate_stim_circuit(
        k=1, noise_model=NoiseModel.uniform_depolarizing(0.001)
    )
    elapsed = time.perf_counter() - started
    emit_result(
        tool="tqec",
        role="backend",
        benchmark="tqec_gallery_cnot_z",
        status="passed",
        runtime_seconds=elapsed,
        notes=(
            f"BlockGraph-to-Stim smoke test at code distance 3; "
            f"Stim qubits={circuit.num_qubits}; instructions={len(circuit)}."
        ),
    )


if __name__ == "__main__":
    main()

