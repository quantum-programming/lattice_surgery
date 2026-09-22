from __future__ import annotations

import argparse
import time

from common import emit_result, load_benchmark
from surface_code_routing.compiled_qcb import compile_qcb
from surface_code_routing.dag import DAG
from surface_code_routing.instructions import CNOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark")
    parser.add_argument("--height", type=int, default=6)
    parser.add_argument("--width", type=int, default=6)
    args = parser.parse_args()

    benchmark = load_benchmark(args.benchmark)
    dag = DAG(benchmark["name"])
    for operation in benchmark["operations"]:
        if operation["gate"] != "cx":
            raise ValueError("The smoke adapter currently accepts only cx operations")
        dag.add_gate(CNOT(f'q_{operation["control"]}', f'q_{operation["target"]}'))

    started = time.perf_counter()
    compiled = compile_qcb(dag, args.height, args.width)
    elapsed = time.perf_counter() - started
    depth = compiled.n_cycles()
    footprint = compiled.width * compiled.height
    emit_result(
        tool="surface_code_compiler",
        role="compiler",
        benchmark=benchmark["name"],
        status="passed",
        runtime_seconds=elapsed,
        logical_depth=depth,
        max_footprint=footprint,
        bounding_box_volume=footprint * depth,
        occupied_patch_time_volume=compiled.space_time_volume(),
        native_volume=compiled.space_time_volume(),
        data_density=benchmark["num_qubits"] / footprint,
        notes=(
            "Python DAG adapter; fixed 6x6 QCB; upstream active space-time volume. "
            "Upstream set traversal can vary the active volume between processes."
        ),
    )


if __name__ == "__main__":
    main()
