from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from common import ROOT, command_error, run_command


def run_smoke(
    benchmark_path: Path,
    *,
    project: Path = ROOT / "external" / "liblsqecc",
    output: Path = ROOT / "work" / "liblsqecc-smoke.json",
) -> dict[str, Any]:
    executable = project / "build" / "lsqecc_slicer"
    if not executable.exists():
        return {
            "status": "blocked",
            "notes": (
                "Build external/liblsqecc/build/lsqecc_slicer before running "
                "this smoke test."
            ),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    completed = run_command([
        str(executable),
        "-I", "qasm",
        "-i", str(benchmark_path),
        "-L", "compact",
        "--graceful",
        "-o", str(output),
        "-f", "stats",
    ])
    elapsed = time.perf_counter() - started
    detail = (completed.stdout + completed.stderr).strip().replace("\n", " ")[-1000:]
    if completed.returncode != 0:
        raise RuntimeError(command_error(completed) or "liblsqecc failed without output")

    return {
        "status": "passed",
        "runtime_seconds": elapsed,
        "notes": detail,
    }
