from __future__ import annotations
import numpy as np
from .circuit import Circuit


def gate_Chi(circuit: Circuit, regs: list, reg_anc: str) -> None:
    for name in regs:
        init = {"name": "Init0", "targets": [name]}
        circuit.add_gate(init)

    for name in regs:
        had = {"name": "H", "targets": [name]}
        circuit.add_gate(had)

    digit = len(regs)
    for idx, name in enumerate(regs):
        angle = np.pi * (2**idx) / (2**digit + 1)
        gate = {"name": "CRZ", "targets": [reg_anc], "angle": angle, "controls": [name]}
        circuit.add_gate(gate)

    meas = {"name": "MeasX", "targets": [reg_anc]}
    circuit.add_gate(meas)


def gate_QFTI(circuit: Circuit, regs: list[str]):
    circuit.add_gate({"name": "H", "targets": [regs[0]]})

    for lsb in range(1, len(regs)):
        for ctr in range(lsb):
            dig = lsb - ctr
            angle = np.pi / (2 * (dig))
            gate = {
                "name": "CRZ",
                "targets": [regs[lsb]],
                "angle": angle,
                "controls": [regs[ctr]],
            }
            circuit.add_gate(gate)
        circuit.add_gate({"name": "H", "targets": [regs[lsb]]})
    for name in regs:
        meas = {"name": "MeasZ", "targets": [name]}
        circuit.add_gate(meas)
