from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from common import load_benchmark


def run_smoke(
    benchmark_path: Path, height: int = 6, width: int = 6
) -> dict[str, Any]:
    from surface_code_routing.compiled_qcb import compile_qcb
    from surface_code_routing.dag import DAG
    from surface_code_routing.instructions import CNOT

    benchmark = load_benchmark(benchmark_path)
    dag = DAG(benchmark["name"])
    for operation in benchmark["operations"]:
        if operation["gate"] != "cx":
            raise ValueError("The smoke adapter currently accepts only cx operations")
        dag.add_gate(CNOT(f'q_{operation["control"]}', f'q_{operation["target"]}'))

    started = time.perf_counter()
    compiled = compile_qcb(dag, height, width)
    elapsed = time.perf_counter() - started
    depth = compiled.n_cycles()
    footprint = compiled.width * compiled.height
    return {
        "status": "passed",
        "runtime_seconds": elapsed,
        "logical_depth": depth,
        "max_footprint": footprint,
        "bounding_box_volume": footprint * depth,
        "occupied_patch_time_volume": compiled.space_time_volume(),
        "native_volume": compiled.space_time_volume(),
        "data_density": benchmark["num_qubits"] / footprint,
        "notes": (
            "Python DAG adapter; fixed 6x6 QCB; upstream active space-time volume. "
            "Upstream set traversal can vary the active volume between processes."
        ),
    }
