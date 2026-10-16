import json
import hashlib
import sys
import unittest
from pathlib import Path

import pyzx as zx
from qiskit import QuantumCircuit
from tqec import BlockGraph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from comparison_common import (  # pyright: ignore[reportMissingImports]
    FAMILIES, ROOT, SEEDS, check_circuit,
)
from tqec_interop import (  # pyright: ignore[reportMissingImports]
    block_graph_metrics,
    build_ours_block_graph,
    build_ours_positioned_zx,
    verify_cnot_block_graph,
)


class ComparisonTest(unittest.TestCase):
    def test_saved_circuit_seed_artifacts(self):
        report = json.loads((ROOT / "circuit_seeds.json").read_text())
        hashes = report["inputs"]
        expected_inputs = {
            f"{family}-seed{seed}" for family in FAMILIES for seed in SEEDS
        }
        self.assertEqual(set(hashes), expected_inputs)
        for name in expected_inputs:
            path = ROOT / "benchmarks" / f"{name}.qasm"
            check_circuit(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), hashes[name])
        patch_record = report["topols_local_patch"]
        patch = ROOT / patch_record["path"]
        self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(),
                         patch_record["sha256"])

        expected_graphs = set()
        for row in report["rows"]:
            tool = "ours" if row["tool"] == "this_work" else "topols"
            stem = f"{tool}-{row['benchmark']}-seed{row['seed']}"
            path = ROOT / "results" / f"{stem}.bgraph"
            if row["status"] != "passed":
                self.assertFalse(path.exists())
                continue
            expected_graphs.add(path.name)
            graph = BlockGraph.from_bgraph(path)
            graph.validate()
            self.assertEqual(graph.name, f"{row['benchmark']}-seed{row['seed']}")
            metrics = row["tqec"]
            self.assertTrue(metrics["circuit_equivalent"])
            self.assertTrue(metrics["bgraph_roundtrip"])
            self.assertEqual(list(graph.bounding_box_size()), metrics["bounding_box"])
            self.assertEqual(graph.spacetime_volume, metrics["occupied_volume"])
        actual_graphs = {path.name for path in
                         (ROOT / "results").glob("*.bgraph")}
        self.assertEqual(actual_graphs, expected_graphs)

    def test_circuit_seed_results(self):
        report = json.loads((ROOT / "circuit_seeds.json").read_text())
        self.assertEqual(report["complete_seeds"], [41, 43, 45, 46, 48])
        self.assertEqual(len(report["inputs"]), 16)
        self.assertEqual(len(report["rows"]), 32)
        failures = report["excluded_failures"]
        self.assertEqual(
            {(row["benchmark"], row["seed"], row["tool"])
             for row in failures},
            {("mqt_min_parallel", seed, "topols") for seed in (42, 44, 47)},
        )
        for row in report["rows"]:
            if row["status"] != "passed":
                self.assertIn("same label", row["error"])
                continue
            self.assertTrue(row["tqec"]["circuit_equivalent"])
            self.assertTrue(row["tqec"]["bgraph_roundtrip"])
        summaries = {(row["benchmark"], row["tool"]): row
                     for row in report["summaries"]}
        self.assertEqual({row["n"] for row in summaries.values()}, {5})
        self.assertAlmostEqual(
            summaries[("mqt_max_parallel", "this_work")]
            ["tqec_occupied_volume"]["mean"], 258.6)
        self.assertAlmostEqual(
            summaries[("mqt_max_parallel", "topols")]
            ["tqec_occupied_volume"]["mean"], 502.6)
        self.assertAlmostEqual(
            summaries[("mqt_min_parallel", "this_work")]
            ["tqec_occupied_volume"]["mean"], 287.2)
        self.assertAlmostEqual(
            summaries[("mqt_min_parallel", "topols")]
            ["tqec_occupied_volume"]["mean"], 445.2)
        self.assertAlmostEqual(
            summaries[("mqt_max_parallel", "this_work")]
            ["total_execution_time"]["mean"], 11.0)
        self.assertAlmostEqual(
            summaries[("mqt_max_parallel", "topols")]
            ["total_execution_time"]["mean"], 23.6)
        self.assertAlmostEqual(
            summaries[("mqt_min_parallel", "this_work")]
            ["total_execution_time"]["mean"], 14.0)
        self.assertAlmostEqual(
            summaries[("mqt_min_parallel", "topols")]
            ["total_execution_time"]["mean"], 21.0)

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
