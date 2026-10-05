"""Compute DoubleTimeSliceScheduler No_Top and No_Kink comparisons.

Usage (from the repository root)::

    python src/ipynb/compute_ignore_topology.py
    python src/ipynb/compute_ignore_topology.py data/circuit/example.in --routing no-kink
    python src/ipynb/compute_ignore_topology.py --output-csv out/table/comparison.csv
    python src/ipynb/compute_ignore_topology.py --output-tex out/table/comparison.tex

With no arguments, compare Original versus Multi under No_Top and No_Kink for
Heisenberg2D indices 0 through 6. Use --routing ignore-topology for the earlier
unlimited-magic baseline. --routing no-top/no-kink selects one finite-factory
condition, using outer factories, naive allocation, two physical layers, and
preparation time 2 by default. The circuit directory is relative to this file,
so running from src/ipynb also works. In a notebook, call
``compare_routing_conditions()`` for all four values per index, or
``compare_heisenberg_circuits(routing="no-kink")`` for one condition.
Finite-factory comparisons include circuit volumes. For an individual file,
``compute_circuit_metrics(path, routing="no-kink")`` returns both metrics.

In a notebook, call ``compute_code_beats(path)``. The result is the maximum
target timing plus one, as in MultiTimeSliceScheduleResult.total_time.
This ports look_ahead_schedule<IgnoreTopologyInfiniteMagic>, including stable
critical-path priority and its ready-instruction traversal. It is a scheduling
baseline, not an optimization over all possible topology-free schedules.

MAGIC_MZ3 and MAGIC_MZ4 include an implicit magic target, giving total arities
three and four. Unlimited magic consumes no slot. For multibody instructions,
the C++ first/last-target dependency blocking is extended to ALL data targets.
Unlimited-magic mode needs no geometry, mapping, or factory parameters. The
finite-factory modes use the deterministic layout in compute_no_kink.py and
validate every resulting schedule, including the multibody routing trees.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import heapq
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Instruction:
    gate: str
    target_ids: tuple[int, ...]  # -1 denotes the implicit magic target.

    @property
    def data_targets(self) -> tuple[int, ...]:
        return tuple(q for q in self.target_ids if q != -1)


def read_circuit(path: str | Path) -> list[Instruction]:
    """Read either circuit format; gates determine arity, not the file suffix."""
    operand_counts = {
        "CX": 2,
        "MAGIC_MOVE": 1,
        "MAGIC_MZZ": 1,
        "MAGIC_MZ3": 2,
        "MAGIC_MZ4": 3,
    }
    instructions = []
    with Path(path).open() as circuit:
        for line_number, line in enumerate(circuit, 1):
            tokens = line.split()
            if not tokens:
                continue
            gate, *operands = tokens
            location = f"{path}:{line_number}"
            if gate not in operand_counts:
                raise ValueError(f"{location}: unknown gate {gate!r}")
            if len(operands) != operand_counts[gate]:
                raise ValueError(
                    f"{location}: {gate} expects {operand_counts[gate]} data operands, "
                    f"got {len(operands)}"
                )
            try:
                targets = tuple(int(q) for q in operands)
            except ValueError as error:
                raise ValueError(f"{location}: qubit IDs must be integers") from error
            if any(q < 0 for q in targets) or len(set(targets)) != len(targets):
                raise ValueError(f"{location}: qubit IDs must be distinct and nonnegative")
            if gate != "CX":
                targets = (-1, *targets)
            instructions.append(Instruction(gate, targets))
    return instructions


def find_path_ignore_topology(
    inst: Instruction, elapsed_code_beat: int, occupied: list[set[int]]
) -> list[tuple[int, int]]:
    """Port the C++ InfiniteMagic path search using qubit IDs as positions.

    ``occupied[t & 1]`` holds occupied targets in time slice t. Each target
    independently selects the earlier free slice; [] means routing must wait.
    """
    path = []
    for target in inst.target_ids:
        if target == -1:
            continue
        for timing in (elapsed_code_beat - 1, elapsed_code_beat):
            if target not in occupied[timing & 1]:
                path.append((timing, target))
                break
        else:
            return []
    return path


def prepare_look_ahead(
    instructions: Iterable[Instruction],
) -> tuple[list[int], list[list[int]], list[int]]:
    """Return original indices in priority order, successors, and in-degrees."""
    instructions = list(instructions)
    count = len(instructions)
    # Backward longest dependency chain, matching reorder_instructions.
    critical_path = [1] * count
    next_instruction: dict[int, int] = {}
    for index in range(count - 1, -1, -1):
        for target in instructions[index].data_targets:
            if target in next_instruction:
                critical_path[index] = max(
                    critical_path[index], critical_path[next_instruction[target]] + 1
                )
            next_instruction[target] = index
    order = sorted(range(count), key=lambda i: -critical_path[i])
    instructions = [instructions[i] for i in order]

    # Build per-qubit dependencies in the reordered list, as the C++ manager does.
    successors: list[list[int]] = [[] for _ in range(count)]
    in_degrees = [0] * count
    previous_instruction: dict[int, int] = {}
    for index, inst in enumerate(instructions):
        if not inst.data_targets or len(set(inst.data_targets)) != len(inst.data_targets):
            raise ValueError("Instructions must have distinct data targets")
        for target in inst.data_targets:
            if target in previous_instruction:
                predecessor = previous_instruction[target]
                successors[predecessor].append(index)
                in_degrees[index] += 1
            previous_instruction[target] = index

    return order, successors, in_degrees


def schedule_code_beats(instructions: Iterable[Instruction]) -> int:
    """Return total code beats using the C++ look-ahead scheduling order."""
    instructions = list(instructions)
    count = len(instructions)
    order, successors, in_degrees = prepare_look_ahead(instructions)
    instructions = [instructions[i] for i in order]

    ready = [i for i, degree in enumerate(in_degrees) if degree == 0]
    heapq.heapify(ready)
    occupied: list[set[int]] = [set(), set()]
    elapsed_code_beat = 1
    total_time = 0
    finished = 0
    while finished < count:
        deferred = []
        while ready:
            index = heapq.heappop(ready)
            path = find_path_ignore_topology(instructions[index], elapsed_code_beat, occupied)
            if not path:
                deferred.append(index)
                continue
            for timing, target in path:
                occupied[timing & 1].add(target)
                # Prevent subsequent uses from going backward in time. For
                # multibody gates this applies to intermediate targets too.
                if timing == elapsed_code_beat:
                    occupied[(timing - 1) & 1].add(target)
                total_time = max(total_time, timing + 1)
            finished += 1
            for successor in successors[index]:
                in_degrees[successor] -= 1
                if in_degrees[successor] == 0:
                    # C++ set traversal cannot revisit indices behind its iterator.
                    if successor > index:
                        heapq.heappush(ready, successor)
                    else:
                        deferred.append(successor)
        ready = deferred
        heapq.heapify(ready)
        elapsed_code_beat += 1
        occupied[elapsed_code_beat & 1].clear()
    return total_time


def compute_code_beats(path: str | Path) -> int:
    """Compute the baseline directly from a circuit file (empty circuit: zero)."""
    return schedule_code_beats(read_circuit(path))


def compute_no_kink_code_beats(
    path: str | Path, *, layer_count: int = 2, magic_prep_time: int = 2,
) -> int:
    """Compute No_Kink with outer factories and naive allocation.

    Uses C++-compatible two-terminal BFS and a BFS/Kruskal tree heuristic for
    multibody gates. See compute_no_kink.py for routing assumptions.
    """
    return compute_circuit_metrics(
        path, routing="no-kink", layer_count=layer_count, magic_prep_time=magic_prep_time,
    )["code_beats"]


def compute_no_top_code_beats(
    path: str | Path, *, layer_count: int = 2, magic_prep_time: int = 2,
) -> int:
    """Compute C++ No_Top (IgnoreTopology), with finite factories and cooldown."""
    return compute_circuit_metrics(
        path, routing="no-top", layer_count=layer_count, magic_prep_time=magic_prep_time,
    )["code_beats"]


def compute_circuit_metrics(
    path: str | Path, *, routing: str = "no-kink",
    layer_count: int = 2, magic_prep_time: int = 2,
) -> dict[str, int]:
    """Compute code beats and circuit volume from one validated finite-factory schedule."""
    from compute_no_kink import schedule_no_kink, validate_schedule

    result = schedule_no_kink(
        read_circuit(path), layer_count=layer_count,
        magic_prep_time=magic_prep_time, routing=routing,
    )
    validate_schedule(result)
    return {"code_beats": result.total_code_beats, "circuit_volume": result.compute_circuit_volume()}


def compare_heisenberg_circuits(
    circuit_dir: str | Path | None = None,
    *, routing: str = "ignore-topology", layer_count: int = 2, magic_prep_time: int = 2,
) -> list[dict[str, int | float]]:
    """Compare the seven Heisenberg2D circuits; reduction is relative to original."""
    directory = (
        Path(circuit_dir)
        if circuit_dir is not None
        else Path(__file__).resolve().parents[2] / "data" / "circuit"
    )
    if routing not in ("ignore-topology", "no-top", "no-kink"):
        raise ValueError(f"Unknown routing condition: {routing}")
    def compute(path: Path) -> dict[str, int]:
        if routing != "ignore-topology":
            return compute_circuit_metrics(
                path, routing=routing, layer_count=layer_count, magic_prep_time=magic_prep_time,
            )
        return {"code_beats": compute_code_beats(path)}

    comparisons = []
    for index in range(7):
        stem = f"result_SELECT_10_Heisenberg2D_cylinder_0.5_0.5_{index}"
        original = compute(directory / f"{stem}.in")
        multi = compute(directory / f"{stem}_multi.in")
        comparison = {"index": index}
        for metric in original:
            comparison[f"original_{metric}"] = original[metric]
            comparison[f"multi_{metric}"] = multi[metric]
            reduction = "reduction_percent" if metric == "code_beats" else "volume_reduction_percent"
            comparison[reduction] = (
                100 * (original[metric] - multi[metric]) / original[metric] if original[metric] else 0.0
            )
        comparisons.append(comparison)
    return comparisons


def compare_routing_conditions(
    circuit_dir: str | Path | None = None,
    *, layer_count: int = 2, magic_prep_time: int = 2,
) -> list[dict[str, int | float]]:
    """Return code beats and volumes for Original/Multi x No_Top/No_Kink."""
    rows = {}
    for routing in ("no-top", "no-kink"):
        for comparison in compare_heisenberg_circuits(
            circuit_dir, routing=routing,
            layer_count=layer_count, magic_prep_time=magic_prep_time,
        ):
            index = comparison["index"]
            row = rows.setdefault(index, {"index": index})
            prefix = routing.replace("-", "_")
            for key, value in comparison.items():
                if key != "index":
                    row[f"{prefix}_{key}"] = value
    return list(rows.values())


def export_comparison_latex(
    rows: list[dict[str, int | float]], path: str | Path,
    *, layer_count: int = 2, magic_prep_time: int = 2,
) -> None:
    """Export one table per condition, combining code beats and circuit volume."""
    lines = [r"% Requires \usepackage{booktabs} and \usepackage{graphicx}."]
    for condition, title, label in (
        ("no_top", r"\texttt{No\_Top}", "tab:original-multi-no-top"),
        ("no_kink", r"\texttt{No\_Kink}", "tab:original-multi-no-kink"),
    ):
        lines.extend([
            r"\begin{table*}[t]", r"  \centering",
            r"  \caption{" + title + r" execution time and circuit volume for Original versus",
            r"    multibody circuits in the size-10",
            r"    Heisenberg2D cylinder instance with parameters $(0.5,0.5)$.",
            f"    The layout uses outer factories, naive allocation, {layer_count} physical",
            f"    layers, and a magic-state preparation time of {magic_prep_time} code beats.",
            r"    Reductions are relative to Original.",
        ])
        if condition == "no_kink":
            lines.extend([
                r"    Multibody routing uses a BFS/Kruskal tree heuristic.",
            ])
        lines.extend([
            r"    Volume counts data-qubit pillars, routed ancillary time-position cells,",
            r"    and preparation cost once per magic instruction; terminal cells are",
            r"    excluded from routing volume, following the C++ finite-factory convention.",
        ])
        lines.extend([
            r"  }", r"  \label{" + label + "}", r"  \resizebox{\textwidth}{!}{%",
            r"    \begin{tabular}{r rrr rrr}", r"      \toprule",
            r"      & \multicolumn{3}{c}{Execution time (code beats)}",
            r"      & \multicolumn{3}{c}{Circuit volume} \\",
            r"      \cmidrule(lr){2-4} \cmidrule(lr){5-7}",
            r"      Index & Original & Multi & Reduction & Original & Multi & Reduction \\",
            r"      \midrule",
        ])
        for row in rows:
            values = [str(row["index"])]
            for metric, reduction in (
                ("code_beats", "reduction_percent"),
                ("circuit_volume", "volume_reduction_percent"),
            ):
                values.extend([
                    str(row[f"{condition}_original_{metric}"]),
                    str(row[f"{condition}_multi_{metric}"]),
                    f"{row[f'{condition}_{reduction}']:.2f}" + r"\%",
                ])
            lines.append("      " + " & ".join(values) + r" \\")
        lines.extend([r"      \bottomrule", r"    \end{tabular}%", r"  }", r"\end{table*}", ""])
    Path(path).write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "circuit", nargs="?", type=Path,
        help="Circuit .in file; omit to compare the seven Heisenberg2D pairs",
    )
    parser.add_argument(
        "--circuit-dir", type=Path,
        help="Directory for comparison files (default: repository data/circuit)",
    )
    parser.add_argument("--routing", choices=("all", "ignore-topology", "no-top", "no-kink"), default="all")
    parser.add_argument("--layers", type=int, choices=(1, 2), default=2, help="Physical layers for finite-factory modes")
    parser.add_argument("--magic-prep-time", type=int, default=2, help="Factory preparation code beats for finite-factory modes")
    parser.add_argument("--output-csv", type=Path, help="Save the comparison table to this CSV")
    parser.add_argument("--output-tex", type=Path, help="Save both metrics as LaTeX tables (requires --routing all)")
    args = parser.parse_args()
    if args.circuit is not None and args.circuit_dir is not None:
        parser.error("--circuit-dir applies only when comparing, without a circuit argument")
    if args.circuit is not None and args.output_csv is not None:
        parser.error("--output-csv applies only to the seven-pair comparison")
    if args.output_tex is not None and (args.circuit is not None or args.routing != "all"):
        parser.error("--output-tex requires the seven-pair comparison with --routing all")
    try:
        if args.circuit is not None:
            conditions = ("no-top", "no-kink") if args.routing == "all" else (args.routing,)
            for condition in conditions:
                if condition == "ignore-topology":
                    total_time = compute_code_beats(args.circuit)
                else:
                    metrics = compute_circuit_metrics(
                        args.circuit, routing=condition, layer_count=args.layers, magic_prep_time=args.magic_prep_time,
                    )
                    print(f"{condition}: {metrics['code_beats']} code beats; circuit volume: {metrics['circuit_volume']}")
                    continue
                print(f"{condition}: {total_time} code beats")
        elif args.routing == "all":
            rows = compare_routing_conditions(
                args.circuit_dir, layer_count=args.layers, magic_prep_time=args.magic_prep_time,
            )
            print(f"Outer factories, naive allocation, {args.layers} layers, preparation time {args.magic_prep_time} (code beats)")
            print(f"{'Index':>5} {'No_Top Orig':>12} {'No_Top Multi':>12} {'Reduction':>10} {'No_Kink Orig':>13} {'No_Kink Multi':>13} {'Reduction':>10}")
            for row in rows:
                print(
                    f"{row['index']:>5} {row['no_top_original_code_beats']:>12} "
                    f"{row['no_top_multi_code_beats']:>12} {row['no_top_reduction_percent']:>9.2f}% "
                    f"{row['no_kink_original_code_beats']:>13} {row['no_kink_multi_code_beats']:>13} "
                    f"{row['no_kink_reduction_percent']:>9.2f}%"
                )
            print("Circuit volume (data pillars + ancillary routing + magic preparation)")
            print(f"{'Index':>5} {'No_Top Orig':>12} {'No_Top Multi':>12} {'Reduction':>10} {'No_Kink Orig':>13} {'No_Kink Multi':>13} {'Reduction':>10}")
            for row in rows:
                print(
                    f"{row['index']:>5} {row['no_top_original_circuit_volume']:>12} "
                    f"{row['no_top_multi_circuit_volume']:>12} {row['no_top_volume_reduction_percent']:>9.2f}% "
                    f"{row['no_kink_original_circuit_volume']:>13} {row['no_kink_multi_circuit_volume']:>13} "
                    f"{row['no_kink_volume_reduction_percent']:>9.2f}%"
                )
            if args.output_csv is not None:
                with args.output_csv.open("w", newline="") as output:
                    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"Saved comparison: {args.output_csv}")
            if args.output_tex is not None:
                export_comparison_latex(
                    rows, args.output_tex, layer_count=args.layers, magic_prep_time=args.magic_prep_time,
                )
                print(f"Saved LaTeX tables: {args.output_tex}")
        else:
            comparisons = compare_heisenberg_circuits(
                args.circuit_dir, routing=args.routing,
                layer_count=args.layers, magic_prep_time=args.magic_prep_time,
            )
            print("Heisenberg2D cylinder, size=10, parameters=0.5, 0.5 (code beats)")
            if args.routing != "ignore-topology":
                print(f"{args.routing}: outer factories, naive allocation, {args.layers} layers, preparation time {args.magic_prep_time}")
            print(f"{'Index':>5} {'Original':>10} {'Multi':>10} {'Reduction':>11}")
            for row in comparisons:
                print(
                    f"{row['index']:>5} {row['original_code_beats']:>10} "
                    f"{row['multi_code_beats']:>10} "
                    f"{row['reduction_percent']:>10.2f}%"
                )
            if args.routing != "ignore-topology":
                print("Circuit volume")
                print(f"{'Index':>5} {'Original':>12} {'Multi':>12} {'Reduction':>11}")
                for row in comparisons:
                    print(
                        f"{row['index']:>5} {row['original_circuit_volume']:>12} "
                        f"{row['multi_circuit_volume']:>12} "
                        f"{row['volume_reduction_percent']:>10.2f}%"
                    )
            if args.output_csv is not None:
                with args.output_csv.open("w", newline="") as output:
                    writer = csv.DictWriter(output, fieldnames=list(comparisons[0]))
                    writer.writeheader()
                    writer.writerows(comparisons)
                print(f"Saved comparison: {args.output_csv}")
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
