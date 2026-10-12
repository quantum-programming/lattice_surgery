"""Export a 2D CNOT schedule from this work to TQEC's textual BGRAPH format."""

import argparse
import json
from pathlib import Path

from qiskit import qasm2  # type: ignore[import-untyped]

from utils.tqec_interop import build_ours_block_graph, export_verified_block_graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qasm", type=Path, help="CNOT-only OpenQASM input")
    parser.add_argument("schedule", type=Path, help="JSON output produced by ours_cnot")
    parser.add_argument("output", type=Path, help="destination .bgraph file")
    args = parser.parse_args()

    circuit = qasm2.load(args.qasm)
    schedule = json.loads(args.schedule.read_text())
    block_graph = build_ours_block_graph(circuit, schedule)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metrics = export_verified_block_graph(circuit, block_graph, args.output)
    if "occupied_volume" in schedule and metrics["occupied_volume"] != schedule["occupied_volume"]:
        raise ValueError("TQEC and the native scheduler disagree on occupied volume.")
    args.output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
