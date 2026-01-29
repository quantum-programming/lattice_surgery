import json
import math
import os
import subprocess
from multiprocessing import Pool
from pathlib import Path
from typing import Tuple

from tqdm import tqdm


def select2json(select_file: str) -> Tuple[str, int, int]:
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
    return (
        json.dumps(res, indent=4),
        max_qubit_id,
        math.ceil(math.sqrt(max_qubit_id)),
    )


def process_by_julia(json_content: str, plane_size: int, circuit_name: str = "") -> str:
    script_dir = Path(__file__).parent
    julia_script_path = script_dir / "visualize_circuit.jl"

    temp_json_path = script_dir / f"temp_circuit_{circuit_name}.json"
    with open(temp_json_path, "w") as temp_file:
        temp_file.write(json_content)

    try:
        tr_dir = script_dir.parent.parent / "TeleportRouter.jl"
        args = [
            "julia",
            "--project=" + str(tr_dir),
            str(julia_script_path),
            str(temp_json_path),
            str(plane_size),
        ]

        result = subprocess.run(args, capture_output=True, text=True, cwd=str(tr_dir))

        if result.returncode != 0:
            raise RuntimeError(f"Julia execution failed: {result.stderr}")
        return result.stdout

    finally:
        os.remove(temp_json_path)


# def compute_result_json(circuit_file):
#     circuit_name = circuit_file.stem
#     json_content, plain_size = select2json(circuit_file)
#     julia_output = process_by_julia(json_content, plain_size, circuit_name)
#     json_result = json.loads(julia_output)
#     json_result["circuit"] = circuit_name
#     return json_result


def visualize(circuit_path, out_path):
    circuit_name = circuit_path.stem

    json_content, data_qubit_count, plain_size = select2json(circuit_path)
    scaled_plain_size = plain_size * 2 + 3
    msf_count = 4 * (plain_size + 1)

    with open(out_path, "w") as f:
        print(scaled_plain_size, scaled_plain_size, 1, file=f)
        print(data_qubit_count, msf_count, file=f)

        data_qubits = [
            (2 * i + 2, 2 * j + 2, 0)
            for i in range(plain_size)
            for j in range(plain_size)
        ]
        data_qubits = data_qubits[:data_qubit_count]
        for pos in data_qubits:
            print(*pos, file=f)

        msfs = set()
        for i in range(0, scaled_plain_size, 2):
            msfs.add((i, 0, 0))
            msfs.add((0, i, 0))
            msfs.add((i, scaled_plain_size - 1, 0))
            msfs.add((scaled_plain_size - 1, i, 0))
        for pos in sorted(msfs):
            print(*pos, file=f)
        print(process_by_julia(json_content, plain_size, circuit_name), file=f)


def main():
    project_dir = Path(__file__).parents[2]
    circuit_dir = project_dir / "data/circuit"
    assert os.path.exists(circuit_dir), "Directory data/circuit does not exist."
    select_files = list(circuit_dir.glob("result_SELECT_4_Fermi*4.in"))
    print(select_files)

    circuit_path = select_files[0]
    output_path = project_dir / f"out/result/EDPC_{circuit_path.stem}.txt"
    visualize(circuit_path, output_path)

    # for select_file in select_files[-1:]:
    #     print(f"Processing {select_file}...")
    #     json_content, plain_size = select2json(select_file)
    #     julia_output = process_by_julia(json_content, plain_size)
    #     json_result = json.loads(julia_output)
    #     json_result["circuit_name"] = select_file
    #     print(json_result)


if __name__ == "__main__":
    main()
