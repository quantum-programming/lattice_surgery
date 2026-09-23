from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import smoke_liblsqecc


class LiblsqeccSmokeTest(unittest.TestCase):
    def test_returns_blocked_when_binary_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = smoke_liblsqecc.run_smoke(
                root / "input.qasm",
                project=root / "project",
                output=root / "output.json",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("Build", result["notes"])

    def test_returns_passed_for_successful_command(self) -> None:
        completed = subprocess.CompletedProcess(
            [],
            0,
            stdout="Total volume: 240\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "project" / "build" / "lsqecc_slicer"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.object(
                smoke_liblsqecc, "run_command", return_value=completed
            ):
                result = smoke_liblsqecc.run_smoke(
                    root / "input.qasm",
                    project=root / "project",
                    output=root / "output.json",
                )

        self.assertEqual(result["status"], "passed")
        self.assertIn("Total volume: 240", result["notes"])
        self.assertIsInstance(result["runtime_seconds"], float)

    def test_raises_for_failed_command(self) -> None:
        completed = subprocess.CompletedProcess(
            [],
            1,
            stdout="",
            stderr="bad input\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "project" / "build" / "lsqecc_slicer"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.object(
                smoke_liblsqecc, "run_command", return_value=completed
            ):
                with self.assertRaisesRegex(RuntimeError, "bad input"):
                    smoke_liblsqecc.run_smoke(
                        root / "input.qasm",
                        project=root / "project",
                        output=root / "output.json",
                    )


if __name__ == "__main__":
    unittest.main()
