import json
import sys
import unittest
from pathlib import Path

from mqt.qecc.cococo.circuit_construction import (
    generate_max_parallel_circuit,
    generate_min_parallel_circuit,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_comparison import BENCHMARKS, check_circuit  # pyright: ignore[reportMissingImports]


class ComparisonTest(unittest.TestCase):
    def test_inputs_match_pinned_generators(self):
        generated = {
            "mqt_max_parallel": generate_max_parallel_circuit(q=6, min_depth=24, seed=45),
            "mqt_min_parallel": generate_min_parallel_circuit(
                q=6, min_depth=24, layer_size=2, seed=45),
        }
        for name in BENCHMARKS:
            circuit = check_circuit(ROOT / "benchmarks" / f"{name}.qasm")
            actual = [tuple(circuit.find_bit(q).index for q in item.qubits)
                      for item in circuit.data]
            self.assertEqual(actual, generated[name])

    def test_checked_in_results(self):
        rows = json.loads((ROOT / "comparison.json").read_text())["rows"]
        self.assertEqual({(row["tool"], row["benchmark"]) for row in rows},
                         {(tool, name) for tool in ("this_work", "topols")
                          for name in BENCHMARKS})
        for row in rows:
            self.assertEqual(row["status"], "passed")
            if row["tool"] == "this_work":
                self.assertEqual(row["allocated_volume"],
                                 row["allocated_sites"] * row["depth"])
            else:
                self.assertEqual(row["bounding_box_volume"],
                                 row["spatial_footprint"] * row["depth"])


if __name__ == "__main__":
    unittest.main()
