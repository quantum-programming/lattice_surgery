from __future__ import annotations
import numpy as np

from .circuit import Circuit
from .gate_prepare import (
    gate_prepare,
    gate_prepare_dag,
    gate_prepare_gray,
    gate_prepare_gray_dag,
)


def multi_control_Z(c: Circuit, control: list, target: str, ancilla: list):
    if len(control) == 0:
        c.add_gate({"name": "Z", "targets": [target]})
    elif len(control) == 1:
        c.add_gate({"name": "CZ", "controls": control, "targets": [target]})
    elif len(control) == 2:
        c.add_gate({"name": "CCZ", "controls": control, "targets": [target]})
    else:
        assert len(ancilla) >= len(control) - 2
        gates = []
        gates.append(
            {
                "name": "CCX",
                "controls": [control[0], control[1]],
                "control_flips": [1, 1],
                "targets": [ancilla[0]],
            }
        )
        for cur in range(2, len(control) - 1):
            gates.append(
                {
                    "name": "CCX",
                    "controls": [control[cur], ancilla[cur - 2]],
                    "control_flips": [1, 1],
                    "targets": [ancilla[cur - 1]],
                }
            )

        for gate in gates:
            c.add_gate(gate)
        c.add_gate(
            {
                "name": "CCZ",
                "controls": [control[len(control) - 1], ancilla[len(control) - 3]],
                "targets": [target],
            }
        )
        for gate in reversed(gates):
            c.add_gate(gate)


def gate_control_reflect(
    c: Circuit,
    reg_digit_bit: str,
    reg_term: list[str],
    reg_term_ancilla: list[str],
    coef: np.ndarray,
) -> None:
    gate_prepare_gray_dag(c, reg_term, coef)
    multi_control_Z(c, reg_term, reg_digit_bit, reg_term_ancilla)
    gate_prepare_gray(c, reg_term, coef)


def gate_reflect(
    c: Circuit, reg_term: list[str], reg_term_ancilla: list[str], coef: np.ndarray
) -> None:
    gate_prepare_gray_dag(c, reg_term, coef)
    multi_control_Z(c, reg_term[:-1], reg_term[-1], reg_term_ancilla)
    gate_prepare_gray(c, reg_term, coef)
