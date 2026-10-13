"""Reproduce the BlockGraph breakdown from the saved comparison outputs.

Run python scripts/analyze_structure.py after scripts/run_comparison.py.
Writes structure_analysis.json and figures/block_graph_breakdown.tex.
Only standard-library modules are used. TopoLS pickles must be trusted local outputs.
"""
import ast
from collections import Counter, defaultdict
import json
from pathlib import Path
import pickle
ROOT = Path(__file__).resolve().parents[1]

def read_graph(path):
    cubes, edges, section = {}, [], None
    for line in path.read_text().splitlines():
        if line.startswith("CUBES:"): section = "cubes"; continue
        if line.startswith("PIPES:"): section = "pipes"; continue
        if not line.startswith("("): continue
        fields = line.split(";")
        if section == "cubes":
            cubes[ast.literal_eval(fields[0])] = fields[4]
        elif section == "pipes":
            edges.append((ast.literal_eval(fields[0]), ast.literal_eval(fields[1])))
    return cubes, edges

report = {}
for name in ("mqt_max_parallel", "mqt_min_parallel"):
    report[name] = {}
    for tool in ("ours", "topols"):
        folder = ROOT / "work/tqec-comparison"
        path = folder / f"ours-{name}.bgraph" if tool == "ours" else folder / f"topols-{name}/{name}.bgraph"
        cubes, edges = read_graph(path)
        adjacent = defaultdict(list)
        axes = Counter()
        for a, b in edges:
            axis = next(i for i in range(3) if a[i] != b[i])
            assert sum(abs(a[i]-b[i]) for i in range(3)) == 1
            adjacent[a].append((b, axis)); adjacent[b].append((a, axis))
            axes["xyz"[axis]] += 1
        categories, layers = Counter(), Counter()
        # Classify geometry, not gates: a degree-two cube subdivides a wire.
        if any(kind not in {"PORT", "XXX", "XXZ", "XZX", "XZZ", "ZXX", "ZXZ", "ZZX", "ZZZ"} for kind in cubes.values()):
            raise ValueError("This unit-cube breakdown does not support Y half-cubes.")
        occupied = {p for p, kind in cubes.items() if kind != "PORT"}
        for point in occupied:
            links = adjacent[point]
            directions = {axis for _, axis in links}
            if len(links) >= 3: kind = "junction"
            elif len(links) == 2 and directions == {2}: kind = "straight_time"
            elif len(links) == 2 and len(directions) == 1: kind = "straight_space"
            elif len(links) == 2: kind = "bend"
            else: kind = "other"
            categories[kind] += 1; layers[point[2]] += 1
        row = {"occupied": len(occupied), "cube_categories": dict(categories), "pipe_axes": dict(axes), "occupied_by_time": dict(sorted(layers.items()))}
        if tool == "ours":
            schedule = json.loads((folder/f"ours-{name}.json").read_text())
            data = {(p[0],p[1],t) for p in schedule["geometry"]["data"] for t in range(schedule["depth"])}
            assert data <= occupied
            row["data_pillar_cubes"] = len(data)
            row["off_pillar_route_cubes"] = len(occupied-data)
        else:
            native = pickle.loads((folder/f"topols-{name}/result/topols/{name}.pkl").read_bytes())
            # Source: TopoLS embedding/ports.py ceiling/seal_brute_frontier.
            # X_old -> X identifies a lifted wire, including fallback lifts.
            # Its occupied union includes endpoints; it is not removable overhead.
            pairs = set()
            for node, position in native["pos_hist"].items():
                label = str(node)
                if not label.endswith("_old"):
                    continue
                base = label[:-4]
                target = native["pos_hist"].get(base)
                if target is None and base.isdigit():
                    target = native["pos_hist"].get(int(base))
                if target is not None:
                    pairs.add(frozenset((tuple(position), tuple(target))))
            lifts = [path for path in native["path_hist"] if frozenset((tuple(path[0]),tuple(path[-1]))) in pairs]
            lift_positions = {tuple(p) for path in lifts for p in path} & occupied
            row["identifiable_lift_paths"] = len(lifts)
            row["cubes_on_identifiable_lifts"] = len(lift_positions)
        report[name][tool] = row

# Reconcile every breakdown with the independently recorded comparison metrics.
recorded = json.loads((ROOT / "comparison.json").read_text())["rows"]
for name, cases in report.items():
    for tool, data in cases.items():
        tool_name = "this_work" if tool == "ours" else "topols"
        row = next(row for row in recorded if row["benchmark"] == name and row["tool"] == tool_name)
        assert data["occupied"] == row["tqec"]["occupied_volume"]
        assert sum(data["cube_categories"].values()) == data["occupied"]
        assert sum(data["pipe_axes"].values()) == row["tqec"]["pipes"]
        assert sum(data["occupied_by_time"].values()) == data["occupied"]
(ROOT / "structure_analysis.json").write_text(json.dumps(report, indent=2) + "\n")

# Generate the manuscript table from these counts, avoiding hand-copied values.
lines = [
    r"% Generated by scripts/analyze_structure.py. Do not edit the counts manually.",
    r"\begin{table}[t]",
    r"    \centering",
    r"    \setlength{\tabcolsep}{3pt}",
    r"    \caption{Occupied-volume breakdown of the compiled BlockGraphs. $J$ counts junctions of degree at least three. Degree-two cubes are classified as straight time-directed segments ($T$), straight spatial segments ($S$), or bends ($B$). These disjoint geometric counts sum to the occupied volume $V$.}",
    r"    \label{tab:topols_comparison}",
    r"    \begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}llrrrrrr@{}}",
    r"        \toprule",
    r"        Circuit & Method & Sites & $J$ & $T$ & $S$ & $B$ & $V$ \\",
    r"        \midrule",
]
markdown = ["| Circuit | Method | Junctions | Time | Space | Bends | Volume |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
for name, cases in report.items():
    label = "Max-parallel" if name == "mqt_max_parallel" else "Min-parallel"
    for tool, data in cases.items():
        method = "Double-slice" if tool == "ours" else "TopoLS"
        tool_name = "this_work" if tool == "ours" else "topols"
        row = next(row for row in recorded if row["benchmark"] == name and row["tool"] == tool_name)
        sites = row["allocated_sites"] if tool == "ours" else row["spatial_footprint"]
        counts = data["cube_categories"]
        if counts.get("other", 0):
            raise ValueError("Unexpected cube geometry cannot be omitted from the table.")
        values = [counts.get(key, 0) for key in ("junction", "straight_time", "straight_space", "bend")]
        values.append(data["occupied"])
        lines.append("        " + " & ".join(map(str, [label, method, sites, *values])) + r" \\")
        markdown.append("| " + " | ".join(map(str, [label, method, *values])) + " |")
lines += [r"        \bottomrule", r"    \end{tabular*}", r"\end{table}"]
(ROOT / "figures").mkdir(exist_ok=True)
(ROOT / "figures/block_graph_breakdown.tex").write_text("\n".join(lines) + "\n")
print("\n".join(markdown))
