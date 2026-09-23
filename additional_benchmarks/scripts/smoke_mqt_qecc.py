from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from common import load_benchmark


def run_smoke(benchmark_path: Path) -> dict[str, Any]:
    import mqt.qecc.cococo.utils_routing as routing
    from mqt.qecc.cococo import layouts

    benchmark = load_benchmark(benchmark_path)
    random.seed(0)

    factories: list[tuple[int, int]] = []
    graph, data_locations, _ = layouts.gen_layout_scalable(
        "triple", 2, 2, factories, remove_edges=False
    )
    if len(data_locations) < benchmark["num_qubits"]:
        raise RuntimeError("Generated MQT layout has too few data locations")
    layout = dict(enumerate(data_locations))
    pairs = []
    for operation in benchmark["operations"]:
        if operation["gate"] != "cx":
            raise ValueError("The smoke adapter currently accepts only cx operations")
        pairs.append((operation["control"], operation["target"]))
    terminals = layouts.translate_layout_circuit(pairs, layout)

    router = routing.BasicRouter(
        graph,
        data_locations,
        factories,
        valid_path="cc",
        t=4,
        metric="exact",
        use_dag=True,
    )
    layers = router.split_layer_terminal_pairs(terminals)
    started = time.perf_counter()
    schedule, _ = router.find_total_vdp_layers_dyn(
        layers, data_locations, router.factory_times, layout, testing=True
    )
    elapsed = time.perf_counter() - started
    if schedule is None:
        raise RuntimeError("MQT router did not find a schedule")

    occupied_volume = 0
    for layer in schedule:
        occupied = set()
        for path in layer.values():
            occupied.update(path)
        occupied_volume += len(occupied)
    footprint = graph.number_of_nodes()
    depth = len(schedule)
    return {
        "status": "passed",
        "runtime_seconds": elapsed,
        "logical_depth": depth,
        "max_footprint": footprint,
        "bounding_box_volume": footprint * depth,
        "occupied_patch_time_volume": occupied_volume,
        "data_density": len(data_locations) / footprint,
        "notes": "Color-code triple layout; BasicRouter; upstream Stim/order checks enabled.",
    }
