import os
import subprocess
from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from tqdm.auto import tqdm

# Configuration settings
pd.options.display.float_format = "{:.3f}".format
plt.rcParams.update(
    {
        "text.usetex": True,
        "font.family": "serif",
        "font.serif": ["Computer Modern Roman"],
        "font.size": 14,
        "axes.labelsize": 18,
        "xtick.labelsize": 18,
        "ytick.labelsize": 18,
    }
)


def compile_main():
    compile_cmd = [
        "g++",
        "-g",
        "src/cpp/main.cpp",
        "-o",
        "src/cpp/main.out",
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-Wfatal-errors",
        "-fdiagnostics-color=always",
        "-DDBG_MACRO_NO_WARNING",
        "-O3",
    ]

    result = subprocess.run(compile_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Compilation failed:")
        print(result.stderr)
        raise RuntimeError("Compilation failed. Please check the errors above.")
    else:
        print("Compilation succeeded.")


def get_data_cache_path(input_file):
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    cache_dir = "fig/evaluate_mapping"
    assert os.path.exists(cache_dir)
    return os.path.join(cache_dir, f"{base_name}_data.csv")


def load_cached_data(input_file):
    cache_path = get_data_cache_path(input_file)
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path)
        if "Total Time" in df.columns:
            df["Total Time"] = pd.to_numeric(df["Total Time"], errors="coerce")
        return df
    return None


def save_data_cache(df, input_file):
    cache_path = get_data_cache_path(input_file)
    df.to_csv(cache_path, index=False)
    print(f"Data cached to: {cache_path}")


def run(input_file, force_recalculate):
    print(f"Input file: {input_file}")

    if not force_recalculate:
        cached_df = load_cached_data(input_file)
        if cached_df is not None:
            create_barplot_visualization(cached_df, input_file)
            return

    print("Running calculations...")
    results = []
    executable = "src/cpp/main.out"
    arg = [
        executable,
        input_file,
        "inner",
        "naive",
        "1",
        "1000000",
        "IgnoreTopologyInfiniteMagic",
    ]
    result = subprocess.run(arg, capture_output=True, text=True)
    total_time = int(result.stdout.splitlines()[0].split()[-1].strip())
    results.append(("Ignore", "TopologyInfiniteMagic", "", "", total_time))
    print("IgnoreTopologyInfiniteMagic")
    print(f"Total time: {total_time} code beats")

    factory_methods = ["outer", "inner"]
    allocation_methods = ["naive", "random", "SA"]
    layer_counts = ["1", "2"]
    sa_iters = ["1000000"]
    routing_algorithms = ["CareKinkParity"]
    args = list(
        product(
            factory_methods,
            allocation_methods,
            layer_counts,
            sa_iters,
            routing_algorithms,
        )
    )

    for factory_m, allocation_m, layer_cnt, sa_iter, routing_alg in tqdm(args):
        arg = [
            executable,
            input_file,
            factory_m,
            allocation_m,
            layer_cnt,
            sa_iter,
            routing_alg,
        ]
        result = subprocess.run(arg, capture_output=True, text=True)

        try:
            total_time = int(result.stdout.splitlines()[0].split()[-1].strip())
        except IndexError as e:
            print(f"{result.stdout=} {result.stderr=}")
            raise e

        results.append((factory_m, allocation_m, layer_cnt, routing_alg, total_time))
        print(f"{result.stderr=}")
        print(
            f"{factory_m=}, {allocation_m=}, {layer_cnt=}, {sa_iter=}, {routing_alg=}"
        )
        print(f"Total time: {total_time} code beats")

    keys = [
        "factory_method",
        "allocation_method",
        "layer_count",
        "routing_algorithm",
        "Total Time",
    ]
    data = [dict(zip(keys, t)) for t in results]
    df = pd.DataFrame(data)

    save_data_cache(df, input_file)
    create_barplot_visualization(df, input_file)


def create_barplot_visualization(df, input_file):
    """Create barplot visualization with seaborn showing ignore topology baseline"""
    ignore_baseline = df[df["factory_method"] == "Ignore"]["Total Time"].iloc[0]
    df_viz = df[df["factory_method"] != "Ignore"].copy()
    df_viz["Total Time"] = pd.to_numeric(df_viz["Total Time"], errors="coerce")

    # Create subplots for layer count 1 and 2
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4), sharey=True)

    # Filter data for each layer count
    df_layer1 = df_viz[df_viz["layer_count"].astype(int) == 1]
    df_layer2 = df_viz[df_viz["layer_count"].astype(int) == 2]

    df_layer1["factory_method"] = df_layer1["factory_method"].replace(
        {"outer": "Outer Factory", "inner": "Inner Factory"}
    )
    df_layer2["factory_method"] = df_layer2["factory_method"].replace(
        {"outer": "Outer Factory", "inner": "Inner Factory"}
    )

    allocation_order = ["SA", "random", "naive"]
    for df_layer in [df_layer1, df_layer2]:
        df_layer["allocation_method"] = pd.Categorical(
            df_layer["allocation_method"], categories=allocation_order, ordered=True
        )
        df_layer = df_layer.sort_values(by=["allocation_method", "factory_method"])

    # Plot for Layer 1
    if not df_layer1.empty:
        sns.barplot(
            data=df_layer1,
            x="allocation_method",
            y="Total Time",
            hue="factory_method",
            ax=ax1,
        )
        ax1.axhline(
            y=ignore_baseline,
            color="k",
            linestyle="dashed",
            linewidth=2,
            label="Lower Bound",
        )
        ax1.set_title("2D Architecture")
        ax1.set_xlabel("Mapping Method")
        ax1.set_ylabel(r"Total Execution Time $T_P$")
        ax1.tick_params(axis="x", rotation=0)
        ax1.legend(fontsize=14, loc="upper left")

    # Plot for Layer 2
    if not df_layer2.empty:
        sns.barplot(
            data=df_layer2,
            x="allocation_method",
            y="Total Time",
            hue="factory_method",
            ax=ax2,
        )
        ax2.axhline(
            y=ignore_baseline,
            color="black",
            linestyle="--",
            linewidth=2,
            label="Lower Bound",
        )
        ax2.set_title("2.5D Architecture")
        ax2.set_xlabel("Mapping Method")
        ax2.tick_params(axis="x", rotation=0)
        ax2.get_legend().remove()

    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    plt.tight_layout()
    assert os.path.exists("fig/evaluate_mapping")
    save_path = f"fig/evaluate_mapping/{input_file.split('/')[-1]}_barplot.pdf"
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    print(f"Barplot saved to: {save_path}")


def main():
    os.chdir(Path(__file__).parent.parent.parent)

    compile_requested = input("Compile the C++ code? (y/n): ").strip().lower() == "y"
    if compile_requested:
        compile_main()

    input_dir = "data/circuit/"
    assert os.path.exists(input_dir)
    input_files = [
        "result_SELECT_10_FermiHubbard2D_cylinder_0_0_6.in",
        "result_SELECT_10_Heisenberg2D_cylinder_0.5_0.5_6.in",
        "result_SELECT_10_Z2LatticeGauge2D_PBC_0_0_6.in",
        "result_SELECT_100_Heisenberg1D_OBC_1_0_6.in",
        "result_SELECT_100_random_local_OBC_0_0_6.in",
        "result_SELECT_100_Schwinger_OBC_0_0_6.in",
    ]

    for input_file in input_files:
        input_path = os.path.join(input_dir, input_file)
        assert os.path.exists(input_path), input_path

        print("-" * 20)
        print(f"Processing {input_path}...")
        run(input_path, force_recalculate=compile_requested)
        print(f"Finished processing {input_path}")


if __name__ == "__main__":
    main()
