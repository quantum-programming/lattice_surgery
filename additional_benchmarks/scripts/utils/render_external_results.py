"""Render tool-specific native results without normalizing their units."""
import json
from pathlib import Path

import matplotlib.pyplot as plt

CASES = ("mqt_max_parallel", "mqt_min_parallel")
LABELS = ("max parallel", "min parallel")


def render(results_path: Path, output: Path) -> None:
    """Draw four independent panels from external_results.json."""
    results = json.loads(results_path.read_text())
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))

    ax = axes[0, 0]
    lib = results["liblsqecc"]["results"]
    bottoms = [0, 0]
    for key, label, color in (
        ("distillation_volume", "distillation", "#ff7f00"),
        ("unused_routing_volume", "unused routing", "#bdbdbd"),
        ("other_active_volume", "other active", "#4daf4a"),
    ):
        values = [lib[case][key] for case in CASES]
        bars = ax.bar(LABELS, values, bottom=bottoms, label=label, color=color)
        ax.bar_label(bars, labels=[str(value) for value in values],
                     label_type="center", fontsize=8)
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]
    for index, total in enumerate(bottoms):
        ax.text(index, total, str(total), ha="center", va="bottom", fontsize=9)
    ax.set_title("libLSQECC: volume breakdown", pad=32)
    ax.set_ylabel("patch-time volume")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=3, frameon=False, fontsize=8)

    ax = axes[0, 1]
    surface = results["surface_code_compiler"]["results"]
    active = [surface[case]["active_space_time_volume"] for case in CASES]
    remaining = [surface[case]["allocated_volume"] - active[index]
                 for index, case in enumerate(CASES)]
    ax.bar(LABELS, active, label="active", color="#377eb8")
    ax.bar(LABELS, remaining, bottom=active, label="remaining allocated", color="#d9d9d9")
    for index, value in enumerate(active):
        ax.text(index, value / 2, str(value), ha="center", va="center", color="white")
    ax.set(title="Surface Code Compiler: fixed 6×6 QCB",
           ylabel="allocated patch-time volume")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    mqt = results["mqt_qecc"]["results"]
    layers = [mqt[case]["routed_layers"] for case in CASES]
    bars = ax.bar(LABELS, layers, color=("#377eb8", "#ff7f00"))
    ax.bar_label(bars)
    ax.set(title="MQT QECC: BasicRouter", ylabel="routed layers")
    ax.text(0.02, 0.95, "108 graph nodes\n24 data locations",
            transform=ax.transAxes, ha="left", va="top", fontsize=9)

    ax = axes[1, 1]
    tqec = results["tqec"]["native_example"]
    ax.axis("off")
    ax.set_title("TQEC: native gallery CNOT")
    for x, value, label, color in (
        (0.17, tqec["correlation_surfaces"], "correlation\nsurfaces", "#4daf4a"),
        (0.50, tqec["stim_qubits"], "Stim\nqubits", "#377eb8"),
        (0.83, tqec["stim_instructions"], "Stim\ninstructions", "#984ea3"),
    ):
        ax.text(x, 0.55, str(value), transform=ax.transAxes, ha="center", va="center",
                fontsize=20, color=color, weight="bold")
        ax.text(x, 0.35, label, transform=ax.transAxes, ha="center", va="center",
                fontsize=9)

    fig.suptitle("Native external-tool outputs (units differ by panel)")
    fig.text(0.5, 0.01, "These native metrics are not a cross-tool ranking.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    output.parent.mkdir(exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
