from __future__ import annotations

import itertools
import json
import os

import numpy as np
from generate_circuit import generate_hamiltonian
from trotter.synthesis.trotter import Trotter1st, Trotter1st_randomized


def process_trotter(
    hamiltonian: dict,
    dt: float,
    epsilon: float,
    is_deterministic: bool = True,
):
    """
    Synthesize the circuit to include only CX, H, S, Sdag, T
    """

    if is_deterministic:
        circuit = Trotter1st(hamiltonian, dt, epsilon)
    else:
        circuit = Trotter1st_randomized(hamiltonian, dt, epsilon)

    # verify(circuit) # this is for SELECT circuit

    gates = []
    creg_cnt = 0
    for gate in circuit:
        if gate["name"] == "CX":
            control = gate["controls"][0]
            target = gate["targets"][0]
            gates.append({"name": "CX", "targets": [target], "controls": [control]})

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

        elif gate["name"] == "CZ":
            # Z = H X H
            control = gate["controls"][0]
            target = gate["targets"][0]
            gates.append({"name": "H", "targets": [target]})
            gates.append({"name": "CX", "targets": [target], "controls": [control]})
            gates.append({"name": "H", "targets": [target]})

        elif gate["name"] in ["H", "S", "T", "Tdag", "Sdag"]:
            target = gate["targets"][0]
            gates.append({"name": gate["name"], "targets": [target]})
            # angle = gate["angle"].real  # angle of RZ gate is real
            # append_RZ_gate(gates, target, angle, epsilon)

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


def generate_trotter(
    size: int,
    ham_type: str,
    boundary_type: str,
    s: float,
    J2: float,
    ham: dict,
    dt: float,
    epsilon: float,
    is_deterministic: bool = True,
):
    gates = process_trotter(ham, dt, epsilon, is_deterministic)

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
            # print(f"{qubit_names=}, {qubit_name=}")
            if qubit_name not in position_dict["seen_names"]:
                if "system" in qubit_name:
                    position_dict["system"].append(qubit_name_2_idx[qubit_name])
                    position_dict["seen_names"].append(qubit_name)
                elif "control_ancilla" in qubit_name:
                    position_dict["control_ancilla"].append(
                        qubit_name_2_idx[qubit_name]
                    )
                    position_dict["seen_names"].append(qubit_name)
                elif "control" in qubit_name:
                    position_dict["control"].append(qubit_name_2_idx[qubit_name])
                    position_dict["seen_names"].append(qubit_name)

    qubit_name_2_idx = str2idx()
    result = ""
    position_dict = {
        "system": [],
        "control_ancilla": [],
        "control": [],
        "seen_names": [],
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

    saved_position_dict = {}
    saved_position_dict.update(system=position_dict["system"])
    saved_position_dict.update(control=position_dict["control"])
    saved_position_dict.update(control_ancilla=position_dict["control_ancilla"])

    det_or_rand = "det" if is_deterministic else "rand"
    with open(
        f"./circuit/result_trotter_{size}_{ham_type}_{boundary_type}_{s}_{J2}_{det_or_rand}.in",
        "w",
    ) as f:
        f.write(result)
    json.dump(
        saved_position_dict,
        open(
            f"./circuit/siteconfig_trotter_{size}_{ham_type}_{boundary_type}_{s}_{J2}_{det_or_rand}.in",
            "w",
        ),
        indent=2,
    )


def generate_FermiHubbard():
    size = [4, 10]
    ham_type = ["FermiHubbard2D"]
    boundary_type = ["cylinder"]
    dt = 0.1
    epsilon = 0.01
    is_deterministic = [True, False]
    args = list(
        itertools.product(
            size,
            ham_type,
            boundary_type,
            [0],
            [0],
        )
    )
    # max_dup_cnt = 4 + 1
    for is_det in is_deterministic:
        args2files(args, dt, epsilon, is_det)


def generate_J1J2():
    size = [4, 10, 20, 30]
    ham_type = ["Heisenberg2D"]
    boundary_type = ["cylinder"]
    s = [1 / 2]
    J2 = [1 / 2]
    args = list(itertools.product(size, ham_type, boundary_type, s, J2))

    dt = 0.1
    epsilon = 0.01
    is_deterministic = [True, False]
    # max_dup_cnt = 4 + 1
    for is_det in is_deterministic:
        args2files(args, dt, epsilon, is_det)


def generate_Schwinger():
    size = [20]
    ham_type = ["Schwinger"]
    boundary_type = ["OBC"]
    dt = 0.1
    epsilon = 0.01
    is_deterministic = [True, False]
    args = list(
        itertools.product(
            size,
            ham_type,
            boundary_type,
            [0],
            [0],
        )
    )
    # max_dup_cnt = 4 + 1
    for is_det in is_deterministic:
        args2files(args, dt, epsilon, is_det)


def generate_random_local():
    size = [10]
    ham_type = ["random_local"]
    boundary_type = ["OBC"]
    args = list(itertools.product(size, ham_type, boundary_type, [0], [0]))

    dt = 0.1
    epsilon = 0.01
    is_deterministic = [True, False]
    for is_det in is_deterministic:
        args2files(args, dt, epsilon, is_det)


def generate_Z2LatticeGauge2D():
    size = [10]
    ham_type = ["Z2LatticeGauge2D"]
    boundary_type = ["PBC"]
    s = [0]
    J2 = [0]
    args = list(itertools.product(size, ham_type, boundary_type, s, J2))

    dt = 0.1
    epsilon = 0.01
    is_deterministic = [True, False]
    for is_det in is_deterministic:
        args2files(args, dt, epsilon, is_det)


def args2files(args, dt, epsilon, is_deterministic):
    for arg in args:
        ham = generate_hamiltonian(*arg)

        for idx in range(len(ham["pauli"])):
            term = ham["pauli"][idx]
            assert len(term) == 2 and term[0].imag == 0
            term_fix = (np.real(term[0]), term[1])
            ham["pauli"][idx] = term_fix
        ham["num_pauli"] = len(ham["pauli"])

        _num_pauli = len(ham["pauli"])
        # max_dup = min(int(np.log2(_num_pauli + 1e-10)), max_dup_cnt)
        # for dup in range(max_dup):
        print("generate : ", arg, f"is_det={is_deterministic}")
        generate_trotter(
            *arg, ham=ham, dt=dt, epsilon=epsilon, is_deterministic=is_deterministic
        )


def main():
    cwd = os.getcwd()
    assert "lattice_surgery" in cwd
    path = cwd.split("lattice_surgery")[0] + "lattice_surgery"
    folderName = path + "/data"
    assert os.path.exists(folderName)
    os.chdir(folderName)

    if not os.path.exists("circuit"):
        os.mkdir("circuit")

    generate_FermiHubbard()
    generate_J1J2()
    # generate_Z2LatticeGauge2D()
    generate_Schwinger()
    generate_random_local()


if __name__ == "__main__":
    main()
