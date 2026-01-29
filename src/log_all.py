import glob
import gzip
import os
import shutil
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

from tqdm import tqdm

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("./cpp/log_all.out"):
    executable_path = "./cpp/log_all.out"
elif os.path.exists("./cpp/log_all"):
    executable_path = "./cpp/log_all"
else:
    raise FileNotFoundError("Executable not found")

PROCESSES = 16


def getFiles() -> list[str]:
    files = glob.glob("../data/circuit/result_*_10_Heisenberg2D_*.in")
    files.sort()
    print(f"{files = }", file=sys.stderr)
    print(f"#files: {len(files)}", file=sys.stderr)
    return files


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


def executeFiles(
    files: list[str],
) -> None:
    tested_parameters = []
    for file in files:
        for factory in ["inner", "outer"]:
            for layer_count in [1, 2]:
                for allocator in ["naive", "random", "SA"]:
                    msf_coeffs = [1, 0.1, 0.01, 0.001] if allocator == "SA" else [0]
                    for msf_coeff in msf_coeffs:
                        msf_prep_times = [0, 1, 2]
                        for msf_prep_time in msf_prep_times:
                            tested_parameters.append(
                                (
                                    file,
                                    factory,
                                    str(layer_count),
                                    allocator,
                                    str(msf_coeff),
                                    str(msf_prep_time),
                                )
                            )
    print(f"{PROCESSES = }")
    print(f"{len(tested_parameters) = }")

    if PROCESSES == 1:  # type: ignore[reportUnnecessaryComparison]
        list(map(execute, tqdm(tested_parameters)))
    else:
        assert PROCESSES > 1
        with Pool(PROCESSES) as p:
            for _ in tqdm(
                p.imap_unordered(execute, tested_parameters),
                total=len(tested_parameters),
            ):
                pass


def main() -> None:
    executeFiles(getFiles())


if __name__ == "__main__":
    main()
