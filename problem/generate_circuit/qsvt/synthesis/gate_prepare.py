from __future__ import annotations
import numpy as np

from .util import get_normalized_vector
from .gate_decomp import state_decomp, convert_gray
from .gate_qrom import create_qrot
from .circuit import Circuit


def get_gate_prepare(c: Circuit, reg: list, reg_ancilla: list, vec: np.ndarray):
    assert 2 ** len(reg) == len(vec)
    assert len(reg) != 0
    raw_gates = state_decomp(vec)
    for key, value in raw_gates.items():
        angle_y = [(item["theta_y"], "Y") for item in value.values()]
        control = reg[:key]
        target = reg[key]
        # print(control, target, angle_y, len(angle_y))
        create_qrot(c, control, target, reg_ancilla[: len(control)], angle_y)

        angle_z = [(item["theta_z"], "Z") for item in value.values()]

        if not np.allclose([v[0] for v in angle_z], np.zeros(len(angle_z))):
            create_qrot(c, control, target, reg_ancilla[: len(control)], angle_z)
    gates = []
    return gates


def gate_prepare(c: Circuit, reg: list, reg_ancilla: list, vec: np.ndarray):
    get_gate_prepare(c, reg, reg_ancilla, vec)


def gate_prepare_dag(c: Circuit, reg: list, reg_ancilla: list, vec: np.ndarray):
    c_tmp = Circuit()
    get_gate_prepare(c_tmp, reg, reg_ancilla, vec)
    rev_gates = []
    for gate in reversed(c.gates):
        if "angle" in gate:
            gate["angle"] *= -1
        rev_gates.append(gate)
    for gate in rev_gates:
        c.add_gate(gate)


def get_gate_prepare_gray(reg: list, vec: np.ndarray):
    assert 2 ** len(reg) == len(vec)
    assert len(reg) != 0
    raw_gates = state_decomp(vec)
    gates = []
    for key, value in raw_gates.items():
        res = convert_gray(key, value)
        gates.extend(res)
    for gate in gates:
        gate["targets"] = [reg[idx] for idx in gate["targets"]]
        if "controls" in gate:
            gate["controls"] = [reg[idx] for idx in gate["controls"]]
    return gates


def gate_prepare_gray(c: Circuit, reg: list, vec: np.ndarray):
    gates = get_gate_prepare_gray(reg, vec)
    for gate in gates:
        c.add_gate(gate)


def gate_prepare_gray_dag(c: Circuit, reg: list, vec: np.ndarray):
    gates = get_gate_prepare_gray(reg, vec)
    rev_gates = []
    for gate in reversed(gates):
        if "angle" in gate:
            gate["angle"] *= -1
        rev_gates.append(gate)
    for gate in rev_gates:
        c.add_gate(gate)


def test_gate_prepare_gray():
    c = Circuit()
    reg = [f"c{i}" for i in range(4)]
    vec = get_normalized_vector(
        np.random.randn(2 ** len(reg)) + np.random.randn(2 ** len(reg)) * 1.0j
    )
    gate_prepare_gray(c, reg, vec)
    print(c)


def test_gate_prepare():
    c = Circuit()
    reg = [f"c{i}" for i in range(4)]
    reg_anc = [f"c{i}" for i in range(4)]
    vec = get_normalized_vector(
        np.random.randn(2 ** len(reg)) + np.random.randn(2 ** len(reg)) * 1.0j
    )
    gate_prepare(c, reg, reg_anc, vec)
    print(c)
