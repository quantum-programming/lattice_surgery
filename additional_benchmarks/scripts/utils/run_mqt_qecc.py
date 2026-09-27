"""Run the MQT QECC color-code lattice-surgery router on one benchmark."""
import random
from pathlib import Path
from typing import Any, cast

from qiskit import qasm2  # type: ignore[import-untyped]


def run(benchmark: Path) -> dict[str, Any]:
    """Route a CNOT circuit on MQT QECC's scalable triple layout."""
    import mqt.qecc.cococo.utils_routing as routing
    from mqt.qecc.cococo import layouts
    from mqt.qecc.cococo.types import Layout

    circuit = qasm2.load(benchmark)
    random.seed(0)
    factories: list[tuple[int, int]] = []
    graph, data_locations, _ = layouts.gen_layout_scalable(
        "triple", 2, 2, factories, remove_edges=False)
    layout: dict[int, tuple[int, int]] = dict(enumerate(data_locations))
    pairs: list[int | tuple[int, int]] = []
    for instruction in circuit.data:
        if instruction.operation.name != "cx":
            raise ValueError("MQT QECC adapter accepts only CNOTs")
        control, target = (circuit.find_bit(q).index for q in instruction.qubits)
        pairs.append((control, target))
    terminals = layouts.translate_layout_circuit(pairs, cast(Layout, layout))
    router = routing.BasicRouter(
        graph, data_locations, factories, valid_path="cc",
        t=4, metric="exact", use_dag=True)
    layers = router.split_layer_terminal_pairs(terminals)

    schedule, _ = router.find_total_vdp_layers_dyn(
        layers, data_locations, router.factory_times, layout, testing=True)
    if schedule is None:
        raise RuntimeError("MQT QECC did not find a routing schedule")
    return {
        "routed_layers": len(schedule),
        "routing_graph_nodes": graph.number_of_nodes(),
        "data_locations": len(data_locations),
    }
