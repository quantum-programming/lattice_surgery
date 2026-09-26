from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from qiskit import qasm2
from qiskit.quantum_info import Operator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_microbenchmarks import (
    BENCHMARKS,
    build_circuit,
    export_visualization,
    operation_signature,
)
from generate_microbenchmarks import generate_benchmarks


class MicrobenchmarkTest(unittest.TestCase):
    def test_checked_in_json_matches_pinned_generators(self) -> None:
        for name, generated in generate_benchmarks().items():
            checked_in = json.loads(
                (ROOT / "benchmarks" / f"{name}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(checked_in, generated)

    def test_corpus_size_and_gate_set(self) -> None:
        for name in BENCHMARKS:
            circuit = build_circuit(ROOT / "benchmarks" / f"{name}.json")
            self.assertEqual(circuit.num_qubits, 6)
            self.assertEqual(circuit.size(), 24)
            self.assertLessEqual(set(circuit.count_ops()), {"cx", "t"})

    def test_qasm_is_an_exact_round_trip(self) -> None:
        for name in BENCHMARKS:
            circuit = build_circuit(ROOT / "benchmarks" / f"{name}.json")
            round_trip = qasm2.loads(qasm2.dumps(circuit))
            self.assertEqual(operation_signature(round_trip), operation_signature(circuit))
            self.assertTrue(Operator(round_trip).equiv(Operator(circuit)))

    def test_visualization_is_png(self) -> None:
        for name in BENCHMARKS:
            path = export_visualization(ROOT / "benchmarks" / f"{name}.json")
            self.assertEqual(path.suffix, ".png")
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
