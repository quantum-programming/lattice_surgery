from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from common import ROOT


TOOLS = {
    "topols": ROOT / "external" / "TopoLS",
    "surface_code_compiler": ROOT / "external" / "Surface_Code_Compiler",
    "mqt_qecc_cococo": ROOT / "external" / "mqt_qecc",
    "tqec": ROOT / "external" / "tqec",
}
EXTRA_INSTALLS = {
    "topols": ["-e", str(ROOT / "external" / "tqec")],
    "surface_code_compiler": ["numpy"],
}
FIELDS = [
    "tool", "role", "benchmark", "commit", "status", "runtime_seconds",
    "logical_depth", "max_footprint", "bounding_box_volume",
    "occupied_patch_time_volume", "native_volume", "data_density", "notes",
]


def env_python(name: str) -> Path:
    suffix = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return ROOT / ".venv" / name / suffix


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def commit(path: Path) -> str:
    result = run([
        "git", "-c", f"safe.directory={path.as_posix()}", "-C", str(path),
        "rev-parse", "HEAD",
    ])
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def setup_environment(name: str, project: Path) -> None:
    python = env_python(name)
    venv = python.parents[1]
    ready = venv / ".ready"
    if python.exists() and ready.exists():
        return
    if not python.exists():
        created = run(["uv", "venv", str(venv), "--python", sys.executable])
        if created.returncode != 0:
            raise RuntimeError(created.stderr or created.stdout)
    installed = run([
        "uv", "pip", "install", "--python", str(python), "-e", str(project),
        *EXTRA_INSTALLS.get(name, []),
    ])
    if installed.returncode != 0:
        raise RuntimeError(installed.stderr or installed.stdout)
    ready.write_text("installed\n", encoding="utf-8")


def parse_last_json(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "status" in value:
            return value
    raise RuntimeError(f"No result JSON found in output:\n{output[-2000:]}")


def execute_adapter(name: str, command: list[str], benchmark: str) -> dict[str, Any]:
    started = time.perf_counter()
    result = run(command)
    elapsed = time.perf_counter() - started
    if result.returncode == 0:
        row = parse_last_json(result.stdout)
    else:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[-1000:]
        row = {
            "tool": name,
            "role": "backend" if name == "tqec" else "compiler",
            "benchmark": benchmark,
            "status": "failed",
            "runtime_seconds": elapsed,
            "notes": detail,
        }
    row["commit"] = commit(TOOLS[name])
    return row


def topols_result() -> dict[str, Any]:
    name = "topols"
    python = env_python(name)
    work = ROOT / "work" / "topols-run"
    benchmark_dir = work / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "benchmarks" / "smoke_cnot.qasm", benchmark_dir / "smoke_cnot.qasm")
    upstream = TOOLS[name] / "docs" / "prog.py"
    command = [
        str(python), str(upstream), "-f", "smoke_cnot", "-b", "4", "-zx", "1",
        "-dir", "1", "-l", "2", "-r", "0", "-s", "1", "-t", "1",
        "-i", "20", "-csv", "smoke", "-sp", "0", "-b0", "0",
    ]
    result = run(command, cwd=work)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[-1000:]
        return {
            "tool": name, "role": "compiler", "benchmark": "smoke_cnot",
            "commit": commit(TOOLS[name]), "status": "failed", "notes": detail,
        }
    collected = run([
        sys.executable, str(ROOT / "scripts" / "collect_topols.py"),
        str(work / "result" / "topols" / "smoke.csv"),
    ])
    row = parse_last_json(collected.stdout)
    row["commit"] = commit(TOOLS[name])
    return row


def blocked_liblsqecc() -> dict[str, Any]:
    project = ROOT / "external" / "liblsqecc"
    executable = ROOT / "work" / "liblsqecc-build" / "Release" / "lsqecc_slicer.exe"
    if executable.exists():
        output = ROOT / "work" / "liblsqecc-smoke.json"
        result = run([
            str(executable), "-I", "qasm", "-i", str(ROOT / "benchmarks" / "smoke_cnot.qasm"),
            "-L", "compact", "--graceful", "-o", str(output), "-f", "stats",
        ])
        return {
            "tool": "liblsqecc", "role": "compiler", "benchmark": "smoke_cnot",
            "commit": commit(project), "status": "passed" if result.returncode == 0 else "failed",
            "notes": (result.stdout + result.stderr).strip().replace("\n", " ")[-1000:],
        }
    return {
        "tool": "liblsqecc", "role": "compiler", "benchmark": "smoke_cnot",
        "commit": commit(project), "status": "blocked",
        "notes": "CMake configuration found MSVC but stopped because SQLite3 headers/libraries are unavailable.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true")
    args = parser.parse_args()
    if args.setup:
        for name, project in TOOLS.items():
            setup_environment(name, project)

    benchmark = ROOT / "benchmarks" / "smoke_cnot.json"
    rows = [blocked_liblsqecc()]
    rows.append(topols_result())
    rows.append(execute_adapter(
        "surface_code_compiler",
        [str(env_python("surface_code_compiler")), str(ROOT / "scripts" / "smoke_surface_code_compiler.py"), str(benchmark)],
        "smoke_cnot",
    ))
    rows.append(execute_adapter(
        "mqt_qecc_cococo",
        [str(env_python("mqt_qecc_cococo")), str(ROOT / "scripts" / "smoke_mqt_qecc.py"), str(benchmark)],
        "smoke_cnot",
    ))
    rows.append(execute_adapter(
        "tqec",
        [str(env_python("tqec")), str(ROOT / "scripts" / "smoke_tqec.py")],
        "tqec_gallery_cnot_z",
    ))

    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    benchmark_bytes = benchmark.read_bytes()
    manifest = {
        "python": sys.version,
        "platform": platform.platform(),
        "benchmark_sha256": hashlib.sha256(benchmark_bytes).hexdigest(),
        "tool_commits": {name: commit(path) for name, path in TOOLS.items()},
        "liblsqecc_commit": commit(ROOT / "external" / "liblsqecc"),
    }
    (results / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (results / "smoke_results.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with (results / "smoke_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
