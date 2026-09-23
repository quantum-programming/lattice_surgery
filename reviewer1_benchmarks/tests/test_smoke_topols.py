from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from smoke_topols import parse_result


class ParseTopoLSResultTest(unittest.TestCase):
    def test_uses_last_csv_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "result.csv"
            csv_path.write_text(
                "compilation_time,time,space,volume\n"
                "1.0,2,10,20\n"
                "1.5,3,25,75\n",
                encoding="utf-8",
            )

            result = parse_result(csv_path)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["runtime_seconds"], 1.5)
        self.assertEqual(result["logical_depth"], 3)
        self.assertEqual(result["max_footprint"], 25)
        self.assertEqual(result["bounding_box_volume"], 75)
        self.assertEqual(result["native_volume"], 75)

    def test_rejects_empty_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "result.csv"
            csv_path.write_text(
                "compilation_time,time,space,volume\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "no CSV rows"):
                parse_result(csv_path)


if __name__ == "__main__":
    unittest.main()
