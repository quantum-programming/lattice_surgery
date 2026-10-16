"""Quantum semantics shared by the CNOT-only comparison adapters."""

from typing import Any

import pyzx as zx
from qiskit import qasm2
from tqec.computation.block_graph import BlockGraph


def cnot_operations(circuit: Any) -> list[tuple[int, int]]:
    """Return the logical control and target of every supported operation."""
    operations = []
    for instruction in circuit.data:
        if instruction.operation.name != "cx":
            raise ValueError("The comparison supports CNOT-only circuits.")
        control, target = (
            circuit.find_bit(qubit).index for qubit in instruction.qubits
        )
        operations.append((control, target))
    return operations


def verify_cnot_block_graph(circuit: Any, block_graph: BlockGraph) -> None:
    """Require the BlockGraph to implement the input circuit on logical ports.

    Port order is logical-qubit order, not spatial order. Following PyZX's
    Circuit.verify_equality, this composes the exported graph with the adjoint
    of the expected circuit, reduces the result, and requires identity wiring.
    The check ignores global scalar and does not claim physical fault tolerance.
    Sources: TQEC BlockGraph.to_zx_graph; PyZX Circuit.verify_equality and
    simplify.full_reduce.
    """
    cnot_operations(circuit)
    block_graph.validate()
    positioned = block_graph.to_zx_graph()
    expected_labels = {
        f"{role}_{qubit}"
        for role in ("input", "output")
        for qubit in range(circuit.num_qubits)
    }
    if set(block_graph.ports) != expected_labels:
        raise ValueError("The exported graph does not have the expected logical ports.")

    exported = positioned.g
    exported.set_inputs(tuple(
        positioned.p2v[block_graph.ports[f"input_{qubit}"]]
        for qubit in range(circuit.num_qubits)
    ))
    exported.set_outputs(tuple(
        positioned.p2v[block_graph.ports[f"output_{qubit}"]]
        for qubit in range(circuit.num_qubits)
    ))

    expected = zx.Circuit.from_qasm(qasm2.dumps(circuit))
    comparison = expected.to_graph().adjoint()
    comparison.compose(exported)
    zx.full_reduce(comparison)
    is_identity = (
        comparison.num_vertices() == 2 * circuit.num_qubits
        and all(comparison.edge_type(edge) == zx.EdgeType.SIMPLE
                for edge in comparison.edges())
        and all(comparison.connected(source, target)
                for source, target in zip(
                    comparison.inputs(), comparison.outputs()
                ))
    )
    if not is_identity:
        raise ValueError("The exported BlockGraph is not equivalent to the input CNOT circuit.")
