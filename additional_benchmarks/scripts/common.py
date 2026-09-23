from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

RESULT_FIELDS = [
    "tool", "role", "benchmark", "commit", "status", "runtime_seconds",
    "logical_depth", "max_footprint", "bounding_box_volume",
    "occupied_patch_time_volume", "native_volume", "data_density", "notes",
]


def load_benchmark(path: str | Path) -> dict[str, Any]:
    benchmark = json.loads(Path(path).read_text(encoding="utf-8"))
    if benchmark.get("schema_version") != 1:
        raise ValueError("Unsupported benchmark schema")
    if benchmark.get("num_qubits", 0) < 1:
        raise ValueError("num_qubits must be positive")
    return benchmark


def result_row(**values: Any) -> dict[str, Any]:
    unexpected = values.keys() - set(RESULT_FIELDS)
    if unexpected:
        raise ValueError(f"Unknown result fields: {sorted(unexpected)}")

    row = dict.fromkeys(RESULT_FIELDS)
    row["notes"] = ""
    row.update(values)
    return row


def run_command(
    command: list[str], *, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def get_commit_id(path: Path) -> str:
    try:
        completed = run_command([
            "git",
            "-c",
            f"safe.directory={path.as_posix()}",
            "-C",
            str(path),
            "rev-parse",
            "HEAD",
        ])
    except OSError:
        return "unknown"
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def command_error(completed: subprocess.CompletedProcess[str]) -> str:
    detail = completed.stderr or completed.stdout
    return detail.strip().replace("\n", " ")[-1000:]
