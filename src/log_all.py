import argparse
import glob
import gzip
import os
import shutil
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

from log_metrics import get_all_tested_parameters_from_config
from tqdm import tqdm

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("./cpp/log_all.out"):
    executable_path = "./cpp/log_all.out"
elif os.path.exists("./cpp/log_all"):
    executable_path = "./cpp/log_all"
else:
    raise FileNotFoundError("Executable not found")

parser = argparse.ArgumentParser(
    description="Run scheduling experiments and save their raw results.",
    formatter_class=argparse.RawTextHelpFormatter,
)
parser.add_argument(
    "--process",
    "-p",
    type=int,
    default=16,
    help="The number of parallel processes.\nDefault: 16",
)
parser.add_argument(
    "--config",
    "-c",
    type=str,
    default="path_histogram_length.json",
    help="Path to the JSON config file that defines experiment parameters.\nDefault: path_histogram_length.json",
)
args = parser.parse_args()
PROCESSES = args.process
CONFIG_PATH = args.config


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

    # Compress the outputs of the C++ executable.
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


def executeFiles(tested_parameters: list[tuple[str, str, str, str, str, str]]) -> None:
    if not tested_parameters:
        print("No parameters to test. Exiting.")
        return

    if PROCESSES == 1:  # type: ignore[reportUnnecessaryComparison]
        print("Running in single process mode...")
        for params in tqdm(tested_parameters):
            execute(params)
    else:
        assert PROCESSES > 1
        print(f"Running in parallel with {PROCESSES} processes...")
        with Pool(PROCESSES) as p:
            for _ in tqdm(
                p.imap_unordered(execute, tested_parameters),
                total=len(tested_parameters),
            ):
                pass


def main() -> None:
    tested_parameters = get_all_tested_parameters_from_config(CONFIG_PATH)
    executeFiles(tested_parameters)


if __name__ == "__main__":
    main()
