import glob
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from multiprocessing import Pool
from typing import DefaultDict, List

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("./cpp/a.out"):
    executable_path = "./cpp/a.out"
elif os.path.exists("./cpp/multi_time_example"):
    executable_path = "./cpp/multi_time_example"
else:
    raise FileNotFoundError("Executable not found")

PROCESSES = 8


def getFiles() -> list[str]:
    files = glob.glob("../data/circuit/result_SELECT_*.in")
    files.sort()
    # files = [file for file in files if "Heisenberg2D" in file and "_6.in" in file]
    print(f"#files: {len(files)}", file=sys.stderr)
    print(f"{files = }", file=sys.stderr)
    return files


def execute(file: str) -> str:
    print("Start: ", file, file=sys.stderr)
    res = subprocess.run([executable_path, file], capture_output=True)
    if res.returncode != 0:
        # red text with ANSI escape code
        print("\033[91m" + "Error" + "\033[0m: " + res.stderr.decode(), file=sys.stderr)
        raise AssertionError
    print("End: ", file, file=sys.stderr)
    return res.stdout.decode()


def executeFiles(
    files: list[str],
) -> tuple[list[str], DefaultDict[str, dict[str, str]]]:
    if PROCESSES == 1:  # type: ignore[reportUnnecessaryComparison]
        results = list(map(execute, files))
    else:
        assert PROCESSES > 1
        with Pool(PROCESSES) as p:
            results = p.map(execute, files)

    file_schedule_result: DefaultDict[str, dict[str, str]] = defaultdict(dict)
    schedules: List[str] = []
    for file, result in zip(files, results):
        lines = result.strip().split("\n")
        for line in lines:
            schedule, _, score = line.partition(": ")
            file_schedule_result[file][schedule] = score
            if schedule not in schedules:
                schedules.append(schedule)
    return schedules, file_schedule_result


def drawTable(
    schedules: list[str],
    file_schedule_result: dict[str, dict[str, str]],
    output_file: str = "",
) -> None:
    header = [""] + (schedules)
    header_inv = {item: i for i, item in enumerate(header)}

    table = [header]
    for file, schedule_result in file_schedule_result.items():
        simple_file_name = file.rpartition("/")[-1]
        row = [simple_file_name] + [""] * len(schedules)
        for schedule, score in schedule_result.items():
            row[header_inv[schedule]] = score
        table.append(row)

    # Transpose the table and get the maximum text length
    text_widths = [max(map(len, column)) for column in zip(*table)]

    if not output_file:
        now_string = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = f"../out/table/table_{now_string}.txt"

    with open(output_file, "w") as f:
        for row in table:
            print(
                *map(
                    lambda width_item: width_item[1].rjust(width_item[0]),
                    zip(text_widths, row),
                ),
                sep=" | ",
                file=f,
            )


def main() -> None:
    files = getFiles()
    schedules, file_schedule_result = executeFiles(files)
    drawTable(schedules, file_schedule_result)


if __name__ == "__main__":
    main()
