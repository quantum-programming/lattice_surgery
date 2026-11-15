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
from analyze_circuit_seeds import pm, summarize  # pyright: ignore[reportMissingImports]
from cnot_semantics import verify_cnot_block_graph  # pyright: ignore[reportMissingImports]
from schedule_to_zx import build_ours_positioned_zx  # pyright: ignore[reportMissingImports]
from tqec_interop import (  # pyright: ignore[reportMissingImports]
    block_graph_metrics,
    build_ours_block_graph,
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
            self.assertEqual(list(graph.bounding_box_size()), metrics["bounding_box"])
            self.assertEqual(graph.spacetime_volume, metrics["occupied_volume"])
        actual_graphs = {path.name for path in
                         (ROOT / "results").glob("*.bgraph")}
        self.assertTrue(expected_graphs <= actual_graphs)

    def test_circuit_seed_results(self):
        report = json.loads((ROOT / "circuit_seeds.json").read_text())
        self.assertEqual(len(report["inputs"]), 16)
        self.assertEqual(len(report["rows"]), 32)
        complete_seeds, summaries = summarize(report["rows"])
        self.assertEqual(report["complete_seeds"], complete_seeds)
        self.assertEqual(report["summaries"], summaries)
        self.assertEqual(complete_seeds, list(SEEDS))
        self.assertEqual(report["excluded_failures"], [])
        expected_cases = {
            (family, seed, tool)
            for family in FAMILIES for seed in SEEDS
            for tool in ("this_work", "topols")
        }
        self.assertEqual(
            {(row["benchmark"], row["seed"], row["tool"])
             for row in report["rows"]}, expected_cases,
        )
        self.assertTrue(all(row["status"] == "passed" for row in report["rows"]))
        self.assertEqual({row["n"] for row in summaries}, {len(SEEDS)})

    def test_manuscript_numbers(self):
        """Keep the published table and prose tied to the saved results."""
        report = json.loads((ROOT / "circuit_seeds.json").read_text())
        summaries = {
            (row["benchmark"], row["tool"]): row
            for row in report["summaries"]
        }
        table = (ROOT / "figures" / "circuit_seeds_comparison.tex").read_text()
        for family, label in (("mqt_max_parallel", "Max-parallel"),
                              ("mqt_min_parallel", "Min-parallel")):
            for tool, method in (("this_work", "Double-slice"), ("topols", "TopoLS")):
                row = summaries[(family, tool)]
                self.assertIn(
                    f"{label} & {method} & {row['n']} & "
                    f"{pm(row['total_execution_time'])} & "
                    f"{pm(row['tqec_occupied_volume'])}", table,
                )
        prose = (ROOT / "topols_comparison.tex").read_text()
        reductions = [round(summaries[(family, "paired_statistics")][
            "tqec_occupied_volume_reduction_percent"]["mean"]) for family in FAMILIES]
        self.assertIn(
            f"${reductions[0]}\\%$ for max-parallel circuits and "
            f"${reductions[1]}\\%$ for min-parallel circuits.", prose,
        )

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
        # TQEC's own CNOT gallery test uses these external stabilizers to check
        # the logical Pauli mappings of its correlation surfaces. Our routed
        # embedding must induce the same set. This supplements ZX tensor
        # equivalence; it does not assert a general cube-orientation theorem.
        self.assertEqual(
            {
                surface.external_stabilizer_on_graph(graph)
                for surface in graph.find_correlation_surfaces()
            },
            {"ZIZI", "ZZIZ", "XIXX", "XXXI"},
        )
        metrics = block_graph_metrics(graph)
        self.assertEqual(graph.num_ports, 4)
        self.assertEqual(metrics["occupied_volume"], 8)
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
