"""Run TQEC's native logical-CNOT compilation example."""
from typing import Any


def run() -> dict[str, Any]:
    """Compile the gallery CNOT block graph to a distance-three Stim circuit."""
    from tqec import Basis, NoiseModel, compile_block_graph
    from tqec.gallery.cnot import cnot

    block_graph = cnot(Basis.Z)
    observables = block_graph.find_correlation_surfaces()
    compiled = compile_block_graph(block_graph, observables=[observables[0]])
    circuit = compiled.generate_stim_circuit(
        k=1, noise_model=NoiseModel.uniform_depolarizing(0.001))
    return {
        "correlation_surfaces": len(observables),
        "stim_qubits": circuit.num_qubits,
        "stim_instructions": len(circuit),
    }
