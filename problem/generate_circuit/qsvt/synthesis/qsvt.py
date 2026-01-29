from typing import Dict

import numpy as np

from .circuit import Circuit
from .gate_qft import gate_Chi, gate_QFTI
from .gate_reflect import gate_control_reflect, gate_reflect
from .gate_select import gate_control_select, gate_select
from .util import get_normalized_vector, get_squared_norm


def QSVT(num_digit: int, num_ham_qubit: int, ham_pauli_list: list):
    c = Circuit()
    # number of qubit in hilbert space of Hamiltonian
    num_hilbert = num_ham_qubit
    # number of terms in Hamiltonian
    num_term = len(ham_pauli_list)

    num_termlog = int(np.log2(num_term - 1e-10)) + 1
    num_digit_anc = 1
    reg_digit = [f"dig_{idx}" for idx in range(num_digit)]
    reg_digit_anc = [f"diga_{idx}" for idx in range(num_digit_anc)]
    reg_term = [f"term_{idx}" for idx in range(num_termlog)]
    reg_term_anc = [f"terma_{idx}" for idx in range(num_termlog)]
    reg_hilbert = [f"hil_{idx}" for idx in range(num_hilbert)]

    coefs = np.ndarray([term[0] for term in ham_pauli_list])
    norm = get_squared_norm(coefs)
    # eps = 2**(-num_digit)
    # if norm > 1 + eps:
    #     num_digit += int(np.log2(norm-eps)) + 1
    coefs = get_normalized_vector(coefs)

    # print(num_digit, num_termlog, num_hilbert)

    print("init")
    gate_Chi(c, reg_digit, reg_digit_anc[0])
    print("first iteration")
    gate_control_select(
        c, reg_digit[0], reg_term, reg_hilbert, reg_term_anc, ham_pauli_list
    )
    gate_control_reflect(c, reg_digit[0], reg_term, reg_term_anc, coefs)

    W = Circuit()
    gate_select(W, reg_term, reg_hilbert, reg_term_anc, ham_pauli_list)
    gate_reflect(W, reg_term, reg_term_anc, coefs)

    for idx, reg in enumerate(reg_digit[1:]):
        print(f"{idx} iteration")
        gate_control_reflect(c, reg, reg_term, reg_term_anc, coefs)
        c.add_gate_list(W.gates * (2**idx))
        gate_control_reflect(c, reg, reg_term, reg_term_anc, coefs)
    print("QFTI")
    gate_QFTI(c, reg_digit)
    print("finish")
    return c


def SELECT(num_ham_qubit: int, ham_pauli_list: list):
    # number of qubit in hilbert space of Hamiltonian
    num_hilbert = num_ham_qubit
    # number of terms in Hamiltonian
    num_term = len(ham_pauli_list)

    num_termlog = int(np.log2(num_term - 1e-10)) + 1
    reg_term = [f"term_{idx}" for idx in range(num_termlog)]
    reg_term_anc = [f"terma_{idx}" for idx in range(num_termlog)]
    reg_hilbert = [f"hil_{idx}" for idx in range(num_hilbert)]

    coefs = np.ndarray([term[0] for term in ham_pauli_list])
    coefs = get_normalized_vector(coefs)
    W = Circuit()
    gate_select(W, reg_term, reg_hilbert, reg_term_anc, ham_pauli_list)
    return W


def verify(circuit):
    gate_list = (
        ["Init0", "MeasZ", "MeasX", "H", "X"]
        + ["RY", "RZ"]
        + ["CX", "CY", "CZ"]
        + ["CRX", "CRY", "CRZ"]
        + ["CCX", "CCZ"]
        + ["barrier"]
    )
    qubit_set = set()
    for gate in circuit.gates:
        assert "name" in gate
        assert "targets" in gate
        assert "target" not in gate
        assert "control" not in gate
        assert "control_flip" not in gate
        assert isinstance(gate["targets"], list)
        assert gate["name"] in gate_list

        for name in gate["targets"]:
            qubit_set.add(name)
        if "controls" in gate:
            assert isinstance(gate["controls"], list)
            for name in gate["controls"]:
                qubit_set.add(name)
        if "control_flips" in gate:
            assert isinstance(gate["control_flips"], list)
        if gate["name"] in ["Init0", "MeasZ", "MeasX", "H", "X"]:
            assert len(gate["targets"]) == 1
        if gate["name"] in ["RY", "RZ"]:
            assert len(gate["targets"]) == 1
            assert "angle" in gate
        if gate["name"] in ["CX", "CY", "CZ"]:
            assert len(gate["targets"]) == 1
            assert len(gate["controls"]) == 1
            assert gate["targets"][0] != gate["controls"][0]
        if gate["name"] in ["CRX", "CRY", "CRZ"]:
            assert len(gate["targets"]) == 1
            assert len(gate["controls"]) == 1
            assert gate["targets"][0] != gate["controls"][0]
            assert "angle" in gate
        if gate["name"] in ["CCX", "CCZ"]:
            assert len(gate["targets"]) == 1
            assert len(gate["controls"]) == 2
            assert gate["targets"][0] != gate["controls"][0]
            assert gate["targets"][0] != gate["controls"][1]
            assert gate["controls"][0] != gate["controls"][1]


def count(circuit: Circuit) -> Dict[str, int | list | str]:
    qubit_set = set()
    num_rot = 0
    num_toffoli = 0
    for gate in circuit.gates:
        # print(gate)
        for name in gate["targets"]:
            qubit_set.add(name)
        if "controls" in gate:
            for name in gate["controls"]:
                qubit_set.add(name)
        if gate["name"] in ["RY", "RZ"]:
            num_rot += 1
        if gate["name"] in ["CRY", "CRZ", "CRX"]:
            num_rot += 2
        if gate["name"] in ["CCX", "CCZ"]:
            num_toffoli += 1

    qubits = list(sorted(list(qubit_set)))
    dic = {
        "num_qubit": len(qubit_set),
        "gate_count": len(circuit.gates),
        "num_rot": num_rot,
        "num_toffoli": num_toffoli,
        "qubits": qubits,
        "circuit": circuit.gates,
    }
    return dic
