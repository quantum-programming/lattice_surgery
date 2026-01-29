import datetime
import glob
import gzip
import io
import os
import shutil
import subprocess
import sys
from itertools import product
from multiprocessing import Pool
from pathlib import Path
import argparse
import json

import pandas as pd
from tqdm import tqdm

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("./cpp/log_metrics.out"):
    executable_path = "./cpp/log_metrics.out"
elif os.path.exists("./cpp/log_metrics"):
    executable_path = "./cpp/log_metrics"
else:
    raise FileNotFoundError("Executable not found")

parser = argparse.ArgumentParser(
    description="Set the number of parallel executions and config file from command-line arguments.",
    # Use RawTextHelpFormatter to properly format the help text
    formatter_class=argparse.RawTextHelpFormatter,
)
parser.add_argument(
    "--process",
    "-p",
    type=int,
    default=4,
    help="The number of parallel processes (integer).\nDefault value: 4",
)
parser.add_argument(
    "--config",
    "-c",
    type=str,
    default="config.json",
    help="Path to the JSON config file defining experiment parameters.\nDefault value: config.json",
)
parser.add_argument(
    "--output",
    "-o",
    type=str,
    default="../out/table/results.csv",
    help="Path to the csv file that saves the experiment results.\nDefault value: ../out/table/results.csv",
)
args = parser.parse_args()
PROCESSES = args.process
CONFIG_PATH = args.config
OUTPUT_PATH = args.output


def execute(parameters: tuple[str, str, str, str, str, str]) -> str:
    input_path, factory, layer_count, allocator, msf_coeff, msf_prep_time = parameters
    # print("Start: ", parameters, file=sys.stderr)
    res = subprocess.run(
        [
            executable_path,
            input_path,
            factory,
            layer_count,
            allocator,
            msf_coeff,
            msf_prep_time,
        ],
        capture_output=True,
    )
    if res.returncode != 0:
        # red text with ANSI escape code
        print("\033[91m" + "Error" + "\033[0m: " + res.stderr.decode(), file=sys.stderr)
        raise AssertionError

    input_path_stem = Path(input_path).stem
    dir_name = f"../out/result/{input_path_stem}/{factory}_{layer_count}_{allocator}_{msf_coeff}_{msf_prep_time}"
    tfs = glob.glob(dir_name + "/*.txt")
    for tf in tfs:
        with open(tf, "rb") as f_in:
            with gzip.open(tf + ".gz", "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(tf)

    # print("End: ", parameters, file=sys.stderr)
    return res.stdout.decode()


def get_all_tested_parameters_from_config(
    config_path: str,
) -> list[tuple[str, str, str, str, str, str]]:
    """Generates parameter combinations from a JSON config file."""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(
            f"\033[91mError\033[0m: Config file not found at {config_path}",
            file=sys.stderr,
        )
        sys.exit(1)
    except json.JSONDecodeError:
        print(
            f"\033[91mError\033[0m: Failed to parse JSON config file {config_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    all_parameters = set()

    if "experiments" not in config or not isinstance(config["experiments"], list):
        print(
            f"\033[91mError\033[0m: JSON config must contain a top-level 'experiments' list.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading parameters from JSON at {CONFIG_PATH}...")

    for experiment in config["experiments"]:
        # Validate experiment structure (basic check)
        required_keys = [
            "name",
            "file_patterns",
            "factories",
            "layer_counts",
            "allocators",
            "msf_prep_times",
        ]
        if not all(key in experiment for key in required_keys):
            print(
                f"\033[91mWarning\033[0m: Skipping experiment '{experiment.get('name', 'Unnamed')}' due to missing keys.",
                file=sys.stderr,
            )
            continue

        print(f"  Loading experiment: {experiment['name']}")

        # Expand file patterns using glob
        file_paths = []
        for pattern in experiment["file_patterns"]:
            expanded_files = glob.glob(pattern)
            if not expanded_files:
                print(
                    f"\033[91mWarning\033[0m: Pattern '{pattern}' in experiment '{experiment['name']}' matched 0 files.",
                    file=sys.stderr,
                )
            file_paths.extend(expanded_files)

        if not file_paths:
            print(
                f"\033[91mWarning\033[0m: No files found for experiment '{experiment['name']}'. Skipping.",
                file=sys.stderr,
            )
            continue

        # Generate parameter combinations
        factories = experiment["factories"]
        layer_counts = experiment["layer_counts"]
        allocator_dict = experiment["allocators"]
        msf_prep_times = experiment["msf_prep_times"]

        # 独立したパラメータの組み合わせを生成 (file, factory, layer_count)
        base_product = product(file_paths, factories, layer_counts)

        for file, factory, layer_count in base_product:
            # 依存関係のあるパラメータ (allocator と msf_coeffs) をループ
            for allocator, msf_coeffs in allocator_dict.items():
                for msf_coeff in msf_coeffs:
                    # 最後のパラメータ (msf_prep_time) をループ
                    for msf_prep_time in msf_prep_times:
                        all_parameters.add(
                            (
                                file,
                                str(factory),
                                str(layer_count),
                                str(allocator),
                                str(msf_coeff),
                                str(msf_prep_time),
                            )
                        )

    print(f"Total unique parameter sets generated: {len(all_parameters)}")
    return list(all_parameters)


def executeFiles(tested_parameters: list[tuple[str, str, str, str, str, str]]) -> None:
    if len(tested_parameters) == 0:
        print("No parameters to test. Exiting.")
        return

    dfs = []
    if PROCESSES == 1:  # type: ignore[reportUnnecessaryComparison]
        print("Running in single process mode...")
        # シングルプロセスでも結果を収集するように修正
        for params in tqdm(tested_parameters):
            csv_str = execute(params)
            dfs.append(pd.read_csv(io.StringIO(csv_str)))
    else:
        assert PROCESSES > 1
        print(f"Running in parallel with {PROCESSES} processes...")
        with Pool(PROCESSES) as p:
            for csv_str in tqdm(
                p.imap_unordered(execute, tested_parameters),
                total=len(tested_parameters),
            ):
                dfs.append(pd.read_csv(io.StringIO(csv_str)))

    merged_df = pd.concat(dfs)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    merged_df.to_csv(OUTPUT_PATH, index=False)
    print(f"Successfully merged results and saved to {OUTPUT_PATH}")


def main() -> None:
    tested_parameters = get_all_tested_parameters_from_config(CONFIG_PATH)
    executeFiles(tested_parameters)


if __name__ == "__main__":
    main()
