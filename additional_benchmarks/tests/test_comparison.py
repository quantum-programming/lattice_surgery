import json
import hashlib
import sys
import unittest
from pathlib import Path

import pyzx as zx
from qiskit import QuantumCircuit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_comparison import BENCHMARKS, check_circuit  # pyright: ignore[reportMissingImports]
from utils.tqec_interop import (  # pyright: ignore[reportMissingImports]
    block_graph_metrics,
    build_ours_block_graph,
    build_ours_positioned_zx,
    verify_cnot_block_graph,
)


class ComparisonTest(unittest.TestCase):
    def test_saved_inputs_match_recorded_hashes(self):
        hashes = json.loads((ROOT / "comparison.json").read_text())["inputs"]
        for name in BENCHMARKS:
            path = ROOT / "benchmarks" / f"{name}.qasm"
            check_circuit(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), hashes[name])

    def test_checked_in_results(self):
        rows = json.loads((ROOT / "comparison.json").read_text())["rows"]
        self.assertEqual({(row["tool"], row["benchmark"]) for row in rows},
                         {(tool, name) for tool in ("this_work", "topols")
                          for name in BENCHMARKS})
        for row in rows:
            self.assertEqual(row["status"], "passed")
            metrics = row["tqec"]
            self.assertTrue(metrics["circuit_equivalent"])
            self.assertTrue(metrics["bgraph_roundtrip"])
            for prefix in ("", "non_port_"):
                x, y, t = metrics[prefix + "bounding_box"]
                self.assertEqual(metrics[prefix + "bounding_box_volume"], x * y * t)
            if row["tool"] == "this_work":
                self.assertEqual(row["allocated_volume"],
                                 row["allocated_sites"] * row["depth"])
            else:
                self.assertEqual(row["bounding_box_volume"],
                                 row["spatial_footprint"] * row["depth"])

    def test_ours_tqec_export_for_cnot_path(self):
        circuit = QuantumCircuit(2)
        circuit.cx(0, 1)
        schedule = {
            "depth": 2,
            "geometry": {
                "data": [[0, 0, 0], [2, 2, 0]],
                "paths": [[
                    [0, 0, 0], [1, 0, 0], [1, 0, 1],
                    [1, 1, 1], [2, 1, 1], [2, 2, 1],
                ]],
            },
        }
        graph = build_ours_block_graph(circuit, schedule)
        verify_cnot_block_graph(circuit, graph)
        metrics = block_graph_metrics(graph)
        self.assertEqual(metrics["ports"], 4)
        self.assertEqual(metrics["occupied_volume"], 8)
        self.assertEqual(metrics["correlation_surfaces"], 4)
        self.assertEqual(metrics["bounding_box"], [3, 3, 4])
        self.assertEqual(metrics["non_port_bounding_box"], [3, 3, 2])
        # A structurally valid graph must still reject the reversed CNOT.
        reversed_circuit = QuantumCircuit(2)
        reversed_circuit.cx(1, 0)
        with self.assertRaisesRegex(ValueError, "not equivalent"):
            verify_cnot_block_graph(reversed_circuit, graph)
        positioned_zx = build_ours_positioned_zx(circuit, schedule)
        expected = zx.Circuit(2)
        expected.add_gate("CNOT", 0, 1)
        self.assertTrue(zx.compare_tensors(expected, positioned_zx.g))


if __name__ == "__main__":
    unittest.main()
