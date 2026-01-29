import json
import math
import os
import subprocess
from multiprocessing import Pool
from pathlib import Path
from typing import Tuple

from tqdm import tqdm

# Parameters

PROCESSES = 16  # Number of processes that execute the julia code

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parents[1].resolve()

TELEPORT_ROUTER_JL_DIR = PROJECT_ROOT / "TeleportRouter.jl"
JULIA_SCRIPT_PATH = SCRIPT_DIR / "process_circuit.jl"

CIRCUIT_DATA_DIR = PROJECT_ROOT / "data/circuit"
CIRCUIT_FILE_GLOB_PATTERN = "result_*_10_Heisenberg2D_*.in"  # Input file pattern

OUTPUT_DIR = PROJECT_ROOT / "out/table"
OUTPUT_FILE_NAME = "EDPC_results.csv"  # Output file name


def select2json(select_file: str) -> Tuple[str, int]:
    res = []
    max_qubit_id = -1
    with open(select_file, "r") as f:
        lines = f.readlines()
        for id, line in enumerate(lines, start=1):
            tokens = line.strip().split()
            op = ""
            qubits = []
            if len(tokens) == 3:
                key, value1, value2 = tokens
                assert key == "CX"
                op = "CX"
                qubits = [int(value1) + 1, int(value2) + 1]
            elif len(tokens) == 2:
                key, value = tokens
                assert key in ["MAGIC_MOVE", "MAGIC_MZZ"]
                op = "tz"
                qubits = [int(value) + 1]
            else:
                raise ValueError(f"Unexpected line format: {line}")
            res.append({"id": id, "op": op, "qubits": qubits, "depends-on": []})
            max_qubit_id = max(max_qubit_id, max(qubits))
    return json.dumps(res, indent=4), max_qubit_id


def process_by_julia(
    json_content: str, max_qubit_id: int, circuit_name: str = ""
) -> str:
    temp_json_path = SCRIPT_DIR / f"temp_circuit_{circuit_name}.json"
    with open(temp_json_path, "w") as temp_file:
        temp_file.write(json_content)

    try:
        args = [
            "julia",
            "--project=" + str(TELEPORT_ROUTER_JL_DIR),
            str(JULIA_SCRIPT_PATH),
            str(temp_json_path),
            str(max_qubit_id),
        ]

        result = subprocess.run(
            args, capture_output=True, text=True, cwd=str(TELEPORT_ROUTER_JL_DIR)
        )

        if result.returncode != 0:
            raise RuntimeError(f"Julia execution failed: {result.stderr}")
        return result.stdout

    finally:
        os.remove(temp_json_path)


def compute_result_json(circuit_file):
    circuit_name = circuit_file.stem
    json_content, max_qubit_id = select2json(circuit_file)
    julia_output = process_by_julia(json_content, max_qubit_id, circuit_name)
    json_result = json.loads(julia_output)
    json_result["circuit"] = circuit_name
    return json_result


def main():
    assert os.path.exists(
        CIRCUIT_DATA_DIR
    ), f"Directory {CIRCUIT_DATA_DIR} does not exist."
    select_files = list(CIRCUIT_DATA_DIR.glob(CIRCUIT_FILE_GLOB_PATTERN))

    if not select_files:
        print(
            f"No files found matching pattern {CIRCUIT_FILE_GLOB_PATTERN} in {CIRCUIT_DATA_DIR}"
        )
        return
    print(f"Found {len(select_files)} circuit files.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / OUTPUT_FILE_NAME

    with open(output_file, "w") as f:
        print("circuit,total_code_beat,circuit_volume", file=f, flush=True)

        if PROCESSES == 1:  # type: ignore[reportUnnecessaryComparison]
            for result in map(compute_result_json, tqdm(select_files)):
                print(
                    f"{result['circuit']},{result['code_beat']},{result['circuit_volume']}",
                    file=f,
                    flush=True,
                )
        else:
            assert PROCESSES > 1
            with Pool(PROCESSES) as p:
                for result in tqdm(
                    p.imap_unordered(compute_result_json, select_files),
                    total=len(select_files),
                ):
                    print(
                        f"{result['circuit']},{result['code_beat']},{result['circuit_volume']}",
                        file=f,
                        flush=True,
                    )
    print(f"Results written to {output_file}")


if __name__ == "__main__":
    main()
