from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path
from typing import Any

from common import ROOT, command_error, run_command


def parse_result(csv_path: Path) -> dict[str, Any]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("TopoLS produced no CSV rows")

    row = rows[-1]
    return {
        "status": "passed",
        "runtime_seconds": float(row["compilation_time"]),
        "logical_depth": int(row["time"]),
        "max_footprint": int(row["space"]),
        "bounding_box_volume": int(row["volume"]),
        "native_volume": int(row["volume"]),
        "notes": "Upstream ZX optimization enabled; one seed; bounding-box volume.",
    }


def run_smoke(
    benchmark_path: Path,
    *,
    project: Path = ROOT / "external" / "TopoLS",
    work: Path = ROOT / "work" / "topols-run",
) -> dict[str, Any]:
    benchmark_dir = work / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(benchmark_path, benchmark_dir / benchmark_path.name)

    upstream = project / "docs" / "prog.py"
    completed = run_command([
        sys.executable,
        str(upstream),
        "-f", benchmark_path.stem,
        "-b", "4",
        "-zx", "1",
        "-dir", "1",
        "-l", "2",
        "-r", "0",
        "-s", "1",
        "-t", "1",
        "-i", "20",
        "-csv", "smoke",
        "-sp", "0",
        "-b0", "0",
    ], cwd=work)
    if completed.returncode != 0:
        raise RuntimeError(command_error(completed) or "TopoLS failed without output")

    return parse_result(work / "result" / "topols" / "smoke.csv")
