from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_smoke
from common import RESULT_FIELDS


class ExecuteCaseTest(unittest.TestCase):
    def case(self, adapter: run_smoke.Adapter) -> run_smoke.SmokeCase:
        return run_smoke.SmokeCase(
            tool="example",
            role="compiler",
            benchmark="smoke",
            repository=Path("/repo"),
            adapter=adapter,
        )

    @patch.object(run_smoke, "get_commit_id", return_value="abc123")
    def test_adds_metadata_and_schema_defaults(self, _commit: object) -> None:
        row = run_smoke.execute_case(
            self.case(lambda: {"status": "passed", "logical_depth": 3})
        )

        self.assertEqual(list(row), RESULT_FIELDS)
        self.assertEqual(row["tool"], "example")
        self.assertEqual(row["commit"], "abc123")
        self.assertEqual(row["logical_depth"], 3)
        self.assertIsNone(row["max_footprint"])

    @patch.object(run_smoke, "get_commit_id", return_value="abc123")
    def test_converts_adapter_exception_to_failed_result(self, _commit: object) -> None:
        def fail() -> dict[str, object]:
            raise RuntimeError("boom")

        row = run_smoke.execute_case(self.case(fail))

        self.assertEqual(row["status"], "failed")
        self.assertIn("RuntimeError: boom", row["notes"])
        self.assertIsInstance(row["runtime_seconds"], float)

    @patch.object(run_smoke, "get_commit_id", return_value="abc123")
    def test_rejects_identity_fields_from_adapter(self, _commit: object) -> None:
        row = run_smoke.execute_case(
            self.case(lambda: {"status": "passed", "tool": "wrong"})
        )

        self.assertEqual(row["status"], "failed")
        self.assertIn("reserved fields", row["notes"])

    @patch.object(run_smoke, "get_commit_id", return_value="abc123")
    def test_preserves_blocked_result(self, _commit: object) -> None:
        row = run_smoke.execute_case(
            self.case(lambda: {"status": "blocked", "notes": "not built"})
        )

        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["notes"], "not built")


class OutputTest(unittest.TestCase):
    def test_writes_json_and_csv_with_the_same_schema(self) -> None:
        row = {
            field: ("" if field == "notes" else None)
            for field in RESULT_FIELDS
        }
        row.update({
            "tool": "example",
            "role": "compiler",
            "benchmark": "smoke",
            "commit": "abc123",
            "status": "passed",
        })

        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            run_smoke.write_results([row], {"tool_commits": {}}, results)

            json_rows = json.loads(
                (results / "smoke_results.json").read_text(encoding="utf-8")
            )
            with (results / "smoke_results.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                csv_rows = list(csv.DictReader(handle))

            self.assertEqual(list(json_rows[0]), RESULT_FIELDS)
            self.assertEqual(list(csv_rows[0]), RESULT_FIELDS)
            self.assertEqual(csv_rows[0]["tool"], "example")


if __name__ == "__main__":
    unittest.main()
