import glob
import os
import subprocess
import sys
from multiprocessing import Pool

os.chdir(os.path.dirname(__file__))
os.chdir("cpp")
if not os.path.exists("main"):
    raise FileNotFoundError("Executable not found")

EXECUTABLE_PATH = "./main"
PROCESSES = 8


def execute(file: str):
    for factory_method in ["inner", "outer"]:
        for allocation_method in ["naive", "random", "SA"]:
            print("Start: ", file, file=sys.stderr)
            res = subprocess.run(
                [
                    EXECUTABLE_PATH,
                    file,
                    factory_method,
                    allocation_method,
                    "1",
                    "1000000",
                    "CareKinkParity",
                ],
                capture_output=True,
            )
            assert res.returncode == 0, f"Error: {res.stderr.decode()}"
            print("End: ", file, file=sys.stderr)


if __name__ == "__main__":
    files = glob.glob("../../data/circuit/result_SELECT_2*.in")
    files.sort()
    print(f"#files: {len(files)}", file=sys.stderr)
    print(f"{files = }", file=sys.stderr)
    with Pool(PROCESSES) as p:
        p.map(execute, files)
