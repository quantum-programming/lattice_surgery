"""Render the four saved BlockGraphs with TopoLS's upstream Matplotlib renderer.

Run python scripts/render_figures.py in the comparison environment.
Writes figures/*.png directly. No browser or network connection is needed.
"""
from pathlib import Path
from typing import Any
import warnings

import matplotlib
matplotlib.use("Agg")  # Save images without opening interactive windows.
import matplotlib.pyplot as plt
from tqec import BlockGraph
from topols.export.visualize import visualize

ROOT = Path(__file__).resolve().parents[1]
FIGURE_SEED = 45

# Upstream renderer and its metadata format:
# https://github.com/tqec/TopoLS/blob/e564d350a596cfea3227e09698733210e2e14dcf/src/topols/export/visualize.py
# https://github.com/tqec/TopoLS/blob/e564d350a596cfea3227e09698733210e2e14dcf/src/topols/export/bgraph.py
# Only adapt the saved graph to its input dictionaries. Geometry, face colours,
# camera and cube size follow the upstream renderer's defaults for both methods.
for name in ("mqt_max_parallel", "mqt_min_parallel"):
    for tool in ("ours", "topols"):
        stem = f"{tool}-{name}"
        graph = BlockGraph.from_bgraph(
            ROOT / "results" / f"{stem}-seed{FIGURE_SEED}.bgraph")
        graph.validate()
        nodes: dict[tuple[int, int, int], dict[str, Any]] = {}
        for cube in graph.cubes:
            p = cube.position
            position = (p.x, p.y, p.z)
            port = None
            if cube.is_port:
                port = {"type": "input" if cube.label.startswith("input_") else "output"}
            nodes[position] = {
                "position": position,
                "tqec": None if cube.is_port else str(cube.kind),
                "other": port,
            }
        edges = {}
        for pipe in graph.pipes:
            a, b = pipe.u.position, pipe.v.position
            first, second = (a.x, a.y, a.z), (b.x, b.y, b.z)
            edges[(first, second)] = (first, second)
        # visualize() always calls show(). Suppress only the expected warning
        # from our noninteractive backend; save its figure at the final path.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="FigureCanvasAgg is non-interactive.*")
            visualize(nodes, edges, stem)
        destination = ROOT / "figures" / f"{stem}.png"
        plt.gcf().savefig(destination, dpi=300, bbox_inches="tight", pad_inches=0.02)
        plt.close("all")
        print(destination, flush=True)
