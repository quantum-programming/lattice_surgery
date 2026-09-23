from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import common


class ResultRowTest(unittest.TestCase):
    def test_result_row_has_the_complete_schema(self) -> None:
        row = common.result_row(tool="example", status="passed")

        self.assertEqual(list(row), common.RESULT_FIELDS)
        self.assertEqual(row["tool"], "example")
        self.assertEqual(row["status"], "passed")
        self.assertIsNone(row["logical_depth"])
        self.assertEqual(row["notes"], "")

    def test_result_row_rejects_unknown_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown result fields"):
            common.result_row(typo_field=1)


class CommitIdTest(unittest.TestCase):
    def test_returns_commit_id_on_success(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="abc123\n", stderr="")
        with patch.object(common, "run_command", return_value=completed):
            self.assertEqual(common.get_commit_id(Path("/repo")), "abc123")

    def test_returns_unknown_when_git_cannot_run(self) -> None:
        with patch.object(common, "run_command", side_effect=OSError("missing")):
            self.assertEqual(common.get_commit_id(Path("/repo")), "unknown")


if __name__ == "__main__":
    unittest.main()
