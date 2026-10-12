"""Export a saved TopoLS compilation pickle to textual TQEC BGRAPH."""
import argparse
import json
from pathlib import Path

from qiskit import qasm2

from utils.tqec_interop import build_topols_block_graph, export_verified_block_graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qasm", type=Path)
    parser.add_argument("compilation", type=Path, help="trusted local TopoLS output .pkl")
    parser.add_argument("output", type=Path, help="destination textual .bgraph file")
    args = parser.parse_args()
    graph = build_topols_block_graph(args.compilation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metrics = export_verified_block_graph(qasm2.load(args.qasm), graph, args.output)
    args.output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
