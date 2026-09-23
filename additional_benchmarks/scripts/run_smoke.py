from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from common import RESULT_FIELDS, ROOT, get_commit_id, result_row
from smoke_liblsqecc import run_smoke as run_liblsqecc
from smoke_mqt_qecc import run_smoke as run_mqt_qecc
from smoke_surface_code_compiler import run_smoke as run_surface_code_compiler
from smoke_topols import run_smoke as run_topols
from smoke_tqec import run_smoke as run_tqec


Adapter = Callable[[], dict[str, Any]]
ADAPTER_FIELDS = set(RESULT_FIELDS) - {"tool", "role", "benchmark", "commit"}


@dataclass(frozen=True)
class SmokeCase:
    tool: str
    role: str
    benchmark: str
    repository: Path
    adapter: Adapter


def smoke_cases() -> list[SmokeCase]:
    benchmark_json = ROOT / "benchmarks" / "smoke_cnot.json"
    benchmark_qasm = ROOT / "benchmarks" / "smoke_cnot.qasm"
    external = ROOT / "external"
    return [
        SmokeCase(
            "liblsqecc",
            "compiler",
            "smoke_cnot",
            external / "liblsqecc",
            lambda: run_liblsqecc(benchmark_qasm),
        ),
        SmokeCase(
            "topols",
            "compiler",
            "smoke_cnot",
            external / "TopoLS",
            lambda: run_topols(benchmark_qasm),
        ),
        SmokeCase(
            "surface_code_compiler",
            "compiler",
            "smoke_cnot",
            external / "Surface_Code_Compiler",
            lambda: run_surface_code_compiler(benchmark_json),
        ),
        SmokeCase(
            "mqt_qecc_cococo",
            "compiler",
            "smoke_cnot",
            external / "mqt_qecc",
            lambda: run_mqt_qecc(benchmark_json),
        ),
        SmokeCase(
            "tqec",
            "backend",
            "tqec_gallery_cnot_z",
            external / "tqec",
            run_tqec,
        ),
    ]


def execute_case(case: SmokeCase) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        values = case.adapter()
        unexpected = values.keys() - ADAPTER_FIELDS
        if unexpected:
            raise ValueError(f"Adapter returned reserved fields: {sorted(unexpected)}")
        if values.get("status") not in {"passed", "failed", "blocked"}:
            raise ValueError("Adapter returned an invalid status")
    except Exception as error:
        values = {
            "status": "failed",
            "runtime_seconds": time.perf_counter() - started,
            "notes": f"{type(error).__name__}: {error}"[-1000:],
        }

    return result_row(
        tool=case.tool,
        role=case.role,
        benchmark=case.benchmark,
        commit=get_commit_id(case.repository),
        **values,
    )


def build_manifest(cases: list[SmokeCase], benchmark: Path) -> dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "benchmark_sha256": hashlib.sha256(benchmark.read_bytes()).hexdigest(),
        "tool_commits": {
            case.tool: get_commit_id(case.repository)
            for case in cases
        },
    }


def write_results(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    results: Path,
) -> None:
    results.mkdir(exist_ok=True)
    (results / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (results / "smoke_results.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    with (results / "smoke_results.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cases = smoke_cases()
    rows = [execute_case(case) for case in cases]
    manifest = build_manifest(cases, ROOT / "benchmarks" / "smoke_cnot.json")
    write_results(rows, manifest, ROOT / "results")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
