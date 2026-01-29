import json
import os

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def load_instance(file_path):
    instructions = []

    assert os.path.exists(file_path)
    with open(file_path, "r") as file:
        lines = file.readlines()

    for line in lines:
        tokens = line.split()
        if tokens[0] == "CX":
            instruction = (int(tokens[1]), int(tokens[2]))
        elif tokens[0] == "MAGIC_MZZ":
            instruction = (int(tokens[1]),)
        elif tokens[0] == "MAGIC_MOVE":
            instruction = (int(tokens[1]),)
        else:
            raise ValueError("Unknown instruction type: {}".format(tokens[0]))
        instructions.append(instruction)

    return instructions


def make_heat_map(instructions, n):
    mtx = [[0 for _ in range(n + 1)] for _ in range(n + 1)]
    for inst in instructions:
        if len(inst) == 2:
            mtx[inst[0]][inst[1]] += 1
            mtx[inst[1]][inst[0]] += 1
        else:
            mtx[inst[0]][n] += 1
            mtx[n][inst[0]] += 1
    return np.array(mtx)


def vis():
    plt.rcParams.update(
        {
            "text.usetex": True,
            "font.family": "serif",
            "font.serif": ["Computer Modern Roman"],
            "font.size": 14,
        }
    )

    for size, ham_type, boundary_type, s, J2, dup in [
        (2, "Heisenberg2D", "cylinder", 0.5, 0.5, 2),
    ]:
        path = f"data/example/result_SELECT_{size}_{ham_type}_{boundary_type}_{s}_{J2}_{dup}.in"
        print(f"path: {path}")

        # Load siteconfig
        siteconfig_path = path.replace("result_", "siteconfig_")
        assert os.path.exists(siteconfig_path), (
            f"Siteconfig file not found: {siteconfig_path}"
        )

        with open(siteconfig_path, "r") as f:
            siteconfig = json.load(f)

        system_qubits = sorted(siteconfig["system"])
        control_qubits = sorted(siteconfig["control"])
        control_ancilla_qubits = sorted(siteconfig["control_ancilla"])
        n = sum(map(len, [system_qubits, control_qubits, control_ancilla_qubits]))

        print(f"System: {system_qubits}")
        print(f"Control: {control_qubits}")
        print(f"Control Ancilla: {control_ancilla_qubits}")

        instructions = load_instance(path)
        data_qubit_count = max(max(inst) for inst in instructions) + 1
        print(f"data_qubit_count: {data_qubit_count}")

        arr = make_heat_map(instructions, data_qubit_count)
        arr_mod = np.where(arr == 0, np.nan, arr)

        fig, ax = plt.subplots(figsize=(8, 6))

        # Assuming qubits are consecutive in each region
        if control_qubits and control_ancilla_qubits:
            control_end = max(control_qubits) + 1
            ancilla_end = max(control_ancilla_qubits) + 1

            # Draw boundaries between regions
            ax.axhline(y=control_end, color="red", linewidth=2, linestyle="--")
            ax.axvline(x=control_end, color="red", linewidth=2, linestyle="--")
            ax.axhline(y=ancilla_end, color="blue", linewidth=2, linestyle="--")
            ax.axvline(x=ancilla_end, color="blue", linewidth=2, linestyle="--")
            ax.axhline(y=n, color="green", linewidth=2, linestyle="--")
            ax.axvline(x=n, color="green", linewidth=2, linestyle="--")

            # Add region labels (center of each region in heatmap coordinates)
            control_mid = (min(control_qubits) + max(control_qubits)) / 2 + 1
            ancilla_mid = (
                min(control_ancilla_qubits) + max(control_ancilla_qubits)
            ) / 2 + 1
            system_mid = (min(system_qubits) + max(system_qubits)) / 2 + 1

            regions = [
                (control_mid, "QPE\nancilla", "red"),
                (ancilla_mid, "Block\nencoding\nancilla", "blue"),
                (system_mid, "System", "green"),
            ]
            for mid, label, color in regions:
                ax.text(
                    mid,
                    -3.8,
                    label,
                    fontsize=18,
                    va="center",
                    ha="center",
                    color=color,
                    weight="bold",
                )

        sns.heatmap(
            arr_mod,
            ax=ax,
            cmap="viridis",
            square=True,
            cbar=True,
            cbar_kws={"label": "Number of instructions"},
        )
        cbar_axes = ax.figure.axes[-1]
        cbar_axes.yaxis.label.set_size(25)  # type: ignore

        ax.set_xlabel("index $i$", fontsize=20)
        ax.set_ylabel("index $j$", fontsize=20)
        ticks = [i * 10 - 1 for i in range(1, 5)]
        labels = list(map(str, [i * 10 for i in range(1, 5)]))
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=20)
        ax.set_yticks(ticks)
        ax.set_yticklabels(labels, fontsize=20)

        ax.axhline(y=0, color="k")
        ax.axhline(y=arr_mod.shape[1], color="k")
        ax.axvline(x=0, color="k")
        ax.axvline(x=arr_mod.shape[0], color="k")

        plt.tight_layout()
        plt.savefig("fig/heatmap.png", bbox_inches="tight", dpi=300)


def main():
    os.chdir(os.path.dirname(__file__))
    os.chdir("../..")
    vis()


if __name__ == "__main__":
    main()
