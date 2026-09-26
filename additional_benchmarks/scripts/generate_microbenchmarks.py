from __future__ import annotations

import json
from typing import Any

from mqt.qecc.cococo.circuit_construction import (
    generate_max_parallel_circuit,
    generate_min_parallel_circuit,
    generate_random_circuit,
)

from common import ROOT, get_commit_id


MQT_COMMIT = "f3c26db10727174af2d2d7c02d1fbee70162a1c0"
NUM_QUBITS = 6
NUM_GATES = 24
SEED = 45


def encode_operations(gates: list[tuple[int, int] | int]) -> list[dict[str, Any]]:
    operations = []
    for gate in gates:
        if isinstance(gate, tuple):
            operations.append({"gate": "cx", "control": gate[0], "target": gate[1]})
        else:
            operations.append({"gate": "t", "target": gate})
    return operations


def benchmark(
    name: str,
    function: str,
    parameters: dict[str, Any],
    gates: list[tuple[int, int] | int],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": name,
        "num_qubits": NUM_QUBITS,
        "generator": {
            "implementation": "mqt.qecc.cococo.circuit_construction",
            "commit": MQT_COMMIT,
            "function": function,
            "parameters": parameters,
        },
        "operations": encode_operations(gates),
    }


def generate_benchmarks() -> dict[str, dict[str, Any]]:
    common = {"q": NUM_QUBITS, "min_depth": NUM_GATES, "seed": SEED}
    return {
        "mqt_max_parallel": benchmark(
            "mqt_max_parallel",
            "generate_max_parallel_circuit",
            common,
            generate_max_parallel_circuit(**common),
        ),
        "mqt_min_parallel": benchmark(
            "mqt_min_parallel",
            "generate_min_parallel_circuit",
            {**common, "layer_size": 2},
            generate_min_parallel_circuit(**common, layer_size=2),
        ),
        "mqt_random_cnot_t": benchmark(
            "mqt_random_cnot_t",
            "generate_random_circuit",
            {**common, "tgate": True, "ratio": 0.5},
            generate_random_circuit(**common, tgate=True, ratio=0.5),
        ),
    }


def main() -> None:
    actual_commit = get_commit_id(ROOT / "external" / "mqt_qecc")
    if actual_commit != MQT_COMMIT:
        raise RuntimeError(f"Expected MQT QECC {MQT_COMMIT}, found {actual_commit}")

    for name, data in generate_benchmarks().items():
        path = ROOT / "benchmarks" / f"{name}.json"
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
