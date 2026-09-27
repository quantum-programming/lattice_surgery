"""Draw our fixed-grid schedule and a TopoLS pipe diagram with shared styling."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

COLORS = {"data": "#377eb8", "factory": "#ff7f00", "route": "#4daf4a",
          0: "#377eb8", 1: "#e41a1c", 2: "#999999"}


def line(ax, points, color, width=2.0, alpha=0.8):
    if len(points) > 1:
        x, y, t = zip(*points)
        ax.plot(x, y, t, color=color, linewidth=width, alpha=alpha)


def cube(ax, point, color, size=42, marker="s"):
    ax.scatter(*point, color=color, s=size, marker=marker, depthshade=False,
               edgecolors="black", linewidths=0.25)


def style(ax, title):
    ax.set_title(title)
    ax.set_xlabel("space x")
    ax.set_ylabel("space y")
    ax.set_zlabel("time")
    ax.view_init(elev=25, azim=-55)
    ax.set_box_aspect((1, 1, 1.15))
    ax.grid(False)


def render(ours_path: Path, topols_path: Path, output: Path) -> None:
    ours = json.loads(ours_path.read_text())
    topols = json.loads(topols_path.read_text())
    fig = plt.figure(figsize=(11, 5))
    left = fig.add_subplot(121, projection="3d")
    right = fig.add_subplot(122, projection="3d")

    depth = ours["depth"]
    geometry = ours["geometry"]
    active = {tuple(point) for point in geometry["data"]}
    for x, y, _ in geometry["data_slot_positions"]:
        cube(left, (x, y, 0), "none" if (x, y, 0) not in active else COLORS["data"])
    for x, y, _ in geometry["data"]:
        line(left, [(x, y, 0), (x, y, depth)], COLORS["data"], 1.2, 0.4)
    for point in geometry["factories"]:
        cube(left, point, COLORS["factory"], 30)
    for path in geometry["paths"]:
        line(left, path, COLORS["route"], 2.2, 0.65)
    style(left, "This work: fixed patch grid")
    left.legend(handles=[
        Line2D([], [], marker="s", linestyle="", color=COLORS["data"], label="data patch"),
        Line2D([], [], marker="s", linestyle="", color=COLORS["factory"], label="MSF"),
        Line2D([], [], color=COLORS["route"], label="routed operation"),
    ], loc="upper left", fontsize=8)

    for path in topols["paths"]:
        line(right, path, "#666666", 1.5, 0.65)
    for node in topols["nodes"]:
        cube(right, node["position"], COLORS.get(node["type"], "#999999"), 24)
    style(right, "TopoLS: ZX-to-3D embedding")
    right.legend(handles=[
        Line2D([], [], marker="s", linestyle="", color=COLORS[0], label="Z spider"),
        Line2D([], [], marker="s", linestyle="", color=COLORS[1], label="X spider"),
        Line2D([], [], color="#666666", label="pipe"),
    ], loc="upper left", fontsize=8)
    fig.tight_layout()
    output.parent.mkdir(exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
