from __future__ import annotations

import argparse
import csv

from common import emit_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--benchmark", default="smoke_cnot")
    args = parser.parse_args()
    with open(args.csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("TopoLS produced no CSV rows")
    row = rows[-1]
    emit_result(
        tool="topols",
        role="compiler",
        benchmark=args.benchmark,
        status="passed",
        runtime_seconds=float(row["compilation_time"]),
        logical_depth=int(row["time"]),
        max_footprint=int(row["space"]),
        bounding_box_volume=int(row["volume"]),
        occupied_patch_time_volume=None,
        native_volume=int(row["volume"]),
        notes="Upstream ZX optimization enabled; one seed; bounding-box volume.",
    )


if __name__ == "__main__":
    main()

