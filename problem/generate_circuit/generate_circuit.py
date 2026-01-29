import itertools
import json
import os
from typing import Any, Dict, List

import numpy as np
from qsvt.hamiltonian import (
    FermiHubbard2D,
    Heisenberg_1D,
    Heisenberg_2D_ext,
    chain_site_single_band,
    random_hamiltonian,
    random_local_hamiltonian,
    schwinger_model,
    single_site_single_band,
    square_site_single_band,
    z2_lattice_gauge,
)
from qsvt.hamiltonian.util import padding_hamiltonian_term_thread
from qsvt.synthesis.circuit import Circuit
from qsvt.synthesis.gate_qrom import (
    create_control_qrom_dist_improve,
    create_control_qrom_dist_improve_earlydrop,
    create_control_qrom_sawtooth,
    create_control_qrom_simple,
)
from qsvt.synthesis.qsvt import verify


def gate_select_simple(
    c: Circuit,
    reg_term: list[str],
    reg_hilbert: list[str],
    reg_term_ancilla: list[str],
    pauli_list: list,
) -> None:
    create_control_qrom_simple(
        c, reg_term, reg_hilbert, reg_term_ancilla, None, pauli_list
    )


def gate_select_sawtooth(
    c: Circuit,
    reg_term: list[str],
    reg_hilbert: list[str],
    reg_term_ancilla: list[str],
    pauli_list: list,
) -> None:
    create_control_qrom_sawtooth(
        c, reg_term, reg_hilbert, reg_term_ancilla, None, pauli_list
    )


def gate_select_dist(
    c: Circuit,
    reg_term: list[str],
    reg_hilbert: list[str],
    reg_term_ancilla: list[str],
    pauli_list: list,
    dup: int,
) -> None:
    create_control_qrom_dist_improve(
        c, reg_term, reg_hilbert, reg_term_ancilla, None, pauli_list, dup
    )


def gate_select_dist_earlydrop(
    c: Circuit,
    reg_term: list[str],
    reg_hilbert: list[str],
    reg_term_ancilla: list[str],
    pauli_list: list,
    dup: int,
) -> None:
    create_control_qrom_dist_improve_earlydrop(
        c, reg_term, reg_hilbert, reg_term_ancilla, None, pauli_list, dup
    )


def SELECT(ham: Any, dup: int):
    num_system = ham["num_qubit"]
    num_term = len(ham["pauli"])
    num_termlog = int(np.log2(num_term - 1e-10)) + 1
    if 2 * num_term < 2**dup:
        raise ValueError("too many parallelization")

    reg_control = [f"control_{idx}" for idx in range(num_termlog)]
    reg_control_ancillary = [f"control_ancilla_{idx}" for idx in range(num_termlog)]

    def to_str(tup):
        return "_".join(map(str, tup))

    reg_system = [f"system_{to_str(ham['pos'][idx])}" for idx in range(num_system)]

    select_circuit = Circuit()

    padded_pauli = padding_hamiltonian_term_thread(ham["pauli"], 2**dup)
    # print(ham["pauli"])
    # print(padded_pauli)
    # print(len(ham["pauli"]), len(padded_pauli), 2**dup)
    gate_select_dist_earlydrop(
        select_circuit,
        reg_control,
        reg_system,
        reg_control_ancillary,
        padded_pauli,
        dup,
    )
    return select_circuit


def process_SELECT(hamiltonian: Any, dup: int = 1) -> List[Dict[str, Any]]:
    circuit = SELECT(hamiltonian, dup)
    verify(circuit)

    gates = []
    creg_cnt = 0
    for gate in circuit.gates:
        if gate["name"] == "CX":
            control = gate["controls"][0]
            target = gate["targets"][0]
            gates.append({"name": "CX", "targets": [target], "controls": [control]})
            # print(gate)
        elif gate["name"] == "CY":
            # https://www.k-pmpstudy.com/entry/2023/02/04/qGateFormulas?utm_source=chatgpt.com
            # Y = S X S^\dag
            control = gate["controls"][0]
            target = gate["targets"][0]
            gates.append({"name": "H", "targets": [target]})
            gates.append({"name": "S", "targets": [target]})
            gates.append({"name": "CX", "targets": [target], "controls": [control]})
            gates.append({"name": "Sdag", "targets": [target]})
            gates.append({"name": "H", "targets": [target]})
            # print(gate)
        elif gate["name"] == "CZ":
            # Z = H X H
            control = gate["controls"][0]
            target = gate["targets"][0]
            gates.append({"name": "H", "targets": [target]})
            gates.append({"name": "CX", "targets": [target], "controls": [control]})
            gates.append({"name": "H", "targets": [target]})
            # int(gate)
        elif gate["name"] == "CCX":
            # https://arxiv.org/abs/2210.14109
            # Fig. S20. (a)
            assert gate["note"] in ["start_t3", "end_t3"]
            if gate["note"] == "start_t3":
                control1 = gate["controls"][0]
                control2 = gate["controls"][1]
                target = gate["targets"][0]
                creg = f"creg{creg_cnt}"
                gates.append({"name": "MAGIC_MOVE", "targets": [target]})
                gates.append(
                    {"name": "CX", "targets": [target], "controls": [control2]}
                )
                gates.append({"name": "Tdag", "targets": [target]})
                gates.append(
                    {"name": "CX", "targets": [target], "controls": [control1]}
                )
                gates.append({"name": "T", "targets": [target]})
                gates.append(
                    {"name": "CX", "targets": [target], "controls": [control2]}
                )
                gates.append({"name": "Tdag", "targets": [target]})
                gates.append({"name": "H", "targets": [target]})
                gates.append({"name": "Sdag", "targets": [target]})
            else:
                control1 = gate["controls"][0]
                control2 = gate["controls"][1]
                target = gate["targets"][0]
                creg = f"creg{creg_cnt}"
                gates.append({"name": "MX", "targets": [target], "output": creg})
                gates.append({"name": "H", "targets": [control2], "condition": creg})
                gates.append(
                    {
                        "name": "CX",
                        "targets": [control2],
                        "controls": [control1],
                        "condition": creg,
                    }
                )
                gates.append({"name": "H", "targets": [control2], "condition": creg})
                creg_cnt += 1
        elif gate["name"] == "barrier":
            continue
        elif gate["name"] == "X":
            continue
        else:
            assert False

    gate_T_replace = []
    for gate in gates:
        if gate["name"] == "T" or gate["name"] == "Tdag":
            creg = f"creg{creg_cnt}"
            gate_T_replace.append(
                {"name": "MAGIC_MZZ", "targets": gate["targets"], "output": creg}
            )
            gate_T_replace.append(
                {"name": "S", "targets": gate["targets"], "condition": creg}
            )
            creg_cnt += 1
        elif gate["name"] == "Sdag":
            gate["name"] = "S"
            gate_T_replace.append(gate)
        else:
            gate_T_replace.append(gate)

    return gate_T_replace


def generate_hamiltonian(
    size: int, ham_type: str, boundary_type: str, s: float, J2: float
) -> Any:
    if ham_type == "Heisenberg1D":
        ham = Heisenberg_1D(size, boundary_type, s, J2)
    elif ham_type == "Heisenberg2D":
        ham = Heisenberg_2D_ext(size, boundary_type, s, J2)
    elif ham_type == "FermiHubbard2D":
        ham = FermiHubbard2D(size, boundary_type)
    elif ham_type == "Schwinger":
        ham = schwinger_model(size)
    elif ham_type == "Z2LatticeGauge2D":
        ham = z2_lattice_gauge(size)
    elif ham_type == "DMFT-single":
        N_bath = int(2 * s - 1)
        ham = single_site_single_band(N_bath)
    elif ham_type == "DMFT1D":
        N_bath = int(2 * s - 1)
        ham = chain_site_single_band(size, N_bath)
    elif ham_type == "DMFT2D":
        N_bath = int(2 * s - 1)
        ham = square_site_single_band(size, N_bath)
    elif ham_type == "random":
        M = int(size**1.5)
        ham = random_hamiltonian(size, M)
    elif ham_type == "random_local":
        M = int(size**1.5)
        ham = random_local_hamiltonian(size, M, 4)
    else:
        assert False, f"Unknown Hamiltonian type: {ham_type}"
    return ham


def generate_SELECT(
    size: int,
    ham_type: str,
    boundary_type: str,
    s: float,
    J2: float,
    ham: Any,
    dup: int,
):
    gates = process_SELECT(ham, dup)

    class str2idx(dict):
        def __init__(self):
            super().__init__()
            self.idx = 0

        def __getitem__(self, key):
            if key not in self:
                self[key] = self.idx
                self.idx += 1
            return super().__getitem__(key)

    def update_position_dict(position_dict, qubit_names, qubit_name_2_idx):
        for qubit_name in qubit_names:
            if qubit_name in position_dict["seen_names"]:
                continue
            position_dict["seen_names"].add(qubit_name)
            if "system" in qubit_name:
                position_dict["system"].append(qubit_name_2_idx[qubit_name])
            elif "control_ancilla" in qubit_name:
                position_dict["control_ancilla"].append(qubit_name_2_idx[qubit_name])
            elif "control" in qubit_name:
                position_dict["control"].append(qubit_name_2_idx[qubit_name])
            else:
                raise ValueError(f"Unknown qubit name: {qubit_name}")

    qubit_name_2_idx = str2idx()
    result = ""
    position_dict = {
        "system": [],
        "control_ancilla": [],
        "control": [],
        "seen_names": set(),
    }
    for gate in gates:
        if gate["name"] == "CX":
            assert "controls" in gate and "targets" in gate
            controls = gate["controls"]
            targets = gate["targets"]
            assert isinstance(controls, list) and len(controls) == 1
            assert isinstance(targets, list) and len(targets) == 1
            result += (
                f"CX {qubit_name_2_idx[controls[0]]} {qubit_name_2_idx[targets[0]]}\n"
            )

            update_position_dict(position_dict, controls, qubit_name_2_idx)
            update_position_dict(position_dict, targets, qubit_name_2_idx)

        elif gate["name"] in ["MAGIC_MOVE", "MAGIC_MZZ"]:
            assert "targets" in gate
            targets = gate["targets"]
            assert isinstance(targets, list) and len(targets) == 1
            targetIndex = qubit_name_2_idx[targets[0]]
            result += f"{gate['name']} {targetIndex}\n"
            update_position_dict(position_dict, targets, qubit_name_2_idx)

        else:
            assert gate["name"] in ["H", "S", "MX"]
            continue

    with open(
        f"./circuit/result_SELECT_{size}_{ham_type}_{boundary_type}_{s}_{J2}_{dup}.in",
        "w",
    ) as f:
        f.write(result)

    saved_position_dict = {}
    saved_position_dict.update(system=position_dict["system"])
    saved_position_dict.update(control=position_dict["control"])
    saved_position_dict.update(control_ancilla=position_dict["control_ancilla"])

    json.dump(
        saved_position_dict,
        open(
            f"./circuit/siteconfig_SELECT_{size}_{ham_type}_{boundary_type}_{s}_{J2}_{dup}.in",
            "w",
        ),
        indent=2,
    )


def args2files(args: List[Any], max_dup_cnt: int) -> None:
    for arg in args:
        ham: Any = generate_hamiltonian(*arg)

        for idx in range(len(ham["pauli"])):
            term = ham["pauli"][idx]
            assert len(term) == 2 and term[0].imag == 0
            term_fix = (np.real(term[0]), term[1])
            ham["pauli"][idx] = term_fix
        ham["num_pauli"] = len(ham["pauli"])

        num_pauli = len(ham["pauli"])
        max_dup = min(int(np.log2(num_pauli + 1e-10)), max_dup_cnt)
        for dup in range(max_dup):
            print("generate : ", arg, dup)
            generate_SELECT(*arg, ham=ham, dup=dup)


def generate_J1J2():
    size = [10]
    ham_type = ["Heisenberg2D"]
    boundary_type = ["cylinder"]
    s = [1 / 2]
    J2 = [1 / 2]
    args = list(itertools.product(size, ham_type, boundary_type, s, J2))
    max_dup_cnt = 6 + 1
    args2files(args, max_dup_cnt)


def generate_S1Chain():
    size = [100]
    ham_type = ["Heisenberg1D"]
    boundary_type = ["OBC"]
    s = [1]
    J2 = [0]
    args = list(itertools.product(size, ham_type, boundary_type, s, J2))
    max_dup_cnt = 6 + 1
    args2files(args, max_dup_cnt)


def _generate_2DHeisenberg_spin1():
    size = [10]
    ham_type = ["Heisenberg2D"]
    max_dup_cnt = 6 + 1
    boundary_type = ["cylinder"]
    s = [1]
    J2 = [0]
    args = list(itertools.product(size, ham_type, boundary_type, s, J2))
    args2files(args, max_dup_cnt)


def generate_random_local():
    size = [100]
    ham_type = ["random_local"]
    boundary_type = ["OBC"]
    args = list(itertools.product(size, ham_type, boundary_type, [0], [0]))
    max_dup_cnt = 6 + 1
    args2files(args, max_dup_cnt)


def generate_FermiHubbard():
    size = [2, 4, 10]
    ham_type = ["FermiHubbard2D"]
    boundary_type = ["cylinder"]
    args = list(itertools.product(size, ham_type, boundary_type, [0], [0]))
    max_dup_cnt = 6 + 1
    args2files(args, max_dup_cnt)


def generate_Schwinger():
    size = [100]
    ham_type = ["Schwinger"]
    boundary_type = ["OBC"]
    args = list(itertools.product(size, ham_type, boundary_type, [0], [0]))
    max_dup_cnt = 6 + 1
    args2files(args, max_dup_cnt)


def generate_Z2LatticeGauge2D():
    size = [10]
    ham_type = ["Z2LatticeGauge2D"]
    boundary_type = ["PBC"]
    s = [0]
    J2 = [0]
    args = list(itertools.product(size, ham_type, boundary_type, s, J2))
    max_dup_cnt = 6 + 1
    args2files(args, max_dup_cnt)


def main():
    cwd = os.getcwd()
    assert "lattice_surgery" in cwd
    path = cwd.split("lattice_surgery")[0] + "lattice_surgery"
    folderName = path + "/data"
    assert os.path.exists(folderName)
    os.chdir(folderName)

    if not os.path.exists("circuit"):
        os.mkdir("circuit")

    generate_J1J2()
    generate_S1Chain()
    generate_FermiHubbard()
    generate_Schwinger()
    generate_Z2LatticeGauge2D()
    generate_random_local()


if __name__ == "__main__":
    main()
