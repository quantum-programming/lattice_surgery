import json
import sys
import unittest
from pathlib import Path

import pyzx as zx
from mqt.qecc.cococo.circuit_construction import (
    generate_max_parallel_circuit,
    generate_min_parallel_circuit,
)
from qiskit import QuantumCircuit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_comparison import BENCHMARKS, check_circuit  # pyright: ignore[reportMissingImports]
from utils.tqec_interop import (  # pyright: ignore[reportMissingImports]
    block_graph_metrics,
    build_ours_block_graph,
    build_ours_positioned_zx,
)


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

    def test_external_results(self):
        results = json.loads((ROOT / "external_results.json").read_text())
        self.assertEqual(set(results), {
            "liblsqecc", "surface_code_compiler", "mqt_qecc", "tqec", "topols"})
        for result in results.values():
            self.assertRegex(result["commit"], r"^[0-9a-f]{40}$")
        for tool in ("liblsqecc", "surface_code_compiler", "mqt_qecc"):
            self.assertEqual(set(results[tool]["results"]), set(BENCHMARKS))
            self.assertTrue(all(result["status"] == "passed"
                                for result in results[tool]["results"].values()))
        self.assertEqual(results["tqec"]["native_example"]["status"], "passed")
        self.assertEqual(results["topols"]["source"], "comparison.json")
        self.assertTrue((ROOT / "figures" / "native_external_results.png").is_file())

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
        metrics = block_graph_metrics(graph)
        self.assertEqual(metrics["ports"], 4)
        self.assertEqual(metrics["occupied_volume"], 8)
        self.assertEqual(metrics["correlation_surfaces"], 4)
        positioned_zx = build_ours_positioned_zx(circuit, schedule)
        expected = zx.Circuit(2)
        expected.add_gate("CNOT", 0, 1)
        self.assertTrue(zx.compare_tensors(expected, positioned_zx.g))


if __name__ == "__main__":
    unittest.main()
