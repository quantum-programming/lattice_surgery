"""Run libLSQECC on one OpenQASM benchmark."""
import re
import subprocess
from pathlib import Path
from typing import Any


def run(benchmark: Path, executable: Path, output: Path) -> dict[str, Any]:
    """Return libLSQECC's compact-layout statistics."""
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run([
        str(executable), "-I", "qasm", "-i", str(benchmark),
        "-L", "compact", "--graceful", "-o", str(output), "-f", "stats",
    ], capture_output=True, text=True, check=True, timeout=300)
    stats = " ".join((completed.stdout + completed.stderr).split())

    def metric(label: str) -> int | None:
        match = re.search(rf"{label}\s+(\d+)", stats)
        return int(match.group(1)) if match else None

    return {
        "slices": metric("Slices"),
        "total_volume": metric("Total volume:"),
        "distillation_volume": metric("Distillation volume:"),
        "unused_routing_volume": metric("Unused routing volume:"),
        "other_active_volume": metric("Other active volume:"),
        "native_stats": stats,
    }
