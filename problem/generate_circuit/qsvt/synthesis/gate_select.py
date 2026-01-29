from __future__ import annotations

import numpy as np
from .gate_qrom import create_control_qrom
from .circuit import Circuit


def gate_control_select(
    c: Circuit,
    control_bit: str,
    reg_term: list[str],
    reg_hilbert: list[str],
    reg_term_ancilla: list[str],
    pauli_list: list,
) -> None:
    create_control_qrom(
        c, reg_term, reg_hilbert, reg_term_ancilla, control_bit, pauli_list
    )


def gate_select(
    c: Circuit,
    reg_term: list[str],
    reg_hilbert: list[str],
    reg_term_ancilla: list[str],
    pauli_list: list,
) -> None:
    create_control_qrom(c, reg_term, reg_hilbert, reg_term_ancilla, None, pauli_list)


def test():
    c = Circuit()
    num = 3
    tgt = 2
    control = [f"c{i}" for i in range(num)]
    ancilla = [f"a{i}" for i in range(num)]
    gcnt = None
    target = [f"t{i}" for i in range(tgt)]
    pauli_list = []
    for ind in range(2**3):
        item = (1.0, [(0, "X")])
        pauli_list.append(item)
    create_control_qrom(c, control, target, ancilla, gcnt, pauli_list)
    print(c)
