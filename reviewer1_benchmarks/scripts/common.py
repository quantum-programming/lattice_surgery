from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_benchmark(path: str | Path) -> dict[str, Any]:
    benchmark = json.loads(Path(path).read_text(encoding="utf-8"))
    if benchmark.get("schema_version") != 1:
        raise ValueError("Unsupported benchmark schema")
    if benchmark.get("num_qubits", 0) < 1:
        raise ValueError("num_qubits must be positive")
    return benchmark


def emit_result(**values: Any) -> None:
    defaults = {
        "runtime_seconds": None,
        "logical_depth": None,
        "max_footprint": None,
        "bounding_box_volume": None,
        "occupied_patch_time_volume": None,
        "native_volume": None,
        "data_density": None,
        "notes": "",
    }
    defaults.update(values)
    print(json.dumps(defaults, sort_keys=True))

