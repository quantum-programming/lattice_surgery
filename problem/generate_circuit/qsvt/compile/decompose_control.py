from qsvt.synthesis.circuit import Circuit


def _proc_control_flips(circuit: Circuit, gate: dict) -> None:
    if "control_flips" not in gate:
        return
    for reg, val in zip(gate["controls"], gate["control_flips"]):
        if val == 0:
            circuit.add_gate({"name": "X", "targets": [reg]})


def _add_CCZ(comp: Circuit, gate: dict) -> None:
    _proc_control_flips(comp, gate)
    comp.add_gate(
        {"name": "CX", "targets": gate["targets"], "controls": [gate["controls"][1]]}
    )
    comp.add_gate({"name": "Tdag", "targets": gate["targets"]})
    comp.add_gate(
        {"name": "CX", "targets": gate["targets"], "controls": [gate["controls"][0]]}
    )
    comp.add_gate({"name": "T", "targets": gate["targets"]})
    comp.add_gate(
        {"name": "CX", "targets": gate["targets"], "controls": [gate["controls"][1]]}
    )
    comp.add_gate({"name": "Tdag", "targets": gate["targets"]})
    comp.add_gate(
        {"name": "CX", "targets": gate["targets"], "controls": [gate["controls"][0]]}
    )
    comp.add_gate({"name": "T", "targets": gate["targets"]})
    comp.add_gate({"name": "T", "targets": [gate["controls"][1]]})
    comp.add_gate(
        {
            "name": "CX",
            "targets": [gate["controls"][1]],
            "controls": [gate["controls"][0]],
        }
    )
    comp.add_gate({"name": "T", "targets": [gate["controls"][0]]})
    comp.add_gate({"name": "Tdag", "targets": [gate["controls"][1]]})
    comp.add_gate(
        {
            "name": "CX",
            "targets": [gate["controls"][1]],
            "controls": [gate["controls"][0]],
        }
    )
    _proc_control_flips(comp, gate)


def _add_RZ(comp: Circuit, gate: dict) -> None:
    assert gate["name"] == "RZ"


def decompose_controls(circuit: Circuit) -> Circuit:
    gate_list = (
        ["Init0", "MeasZ", "MeasX", "H", "X"]
        + ["RY", "RZ"]
        + ["CX", "CY", "CZ"]
        + ["CRX", "CRY", "CRZ"]
        + ["CCX", "CCZ"]
        + ["barrier"]
    )
    comp = Circuit()
    for gate in circuit.gates:
        assert gate["name"] in gate_list
        if gate["name"] == "CX":
            _proc_control_flips(comp, gate)
            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            _proc_control_flips(comp, gate)

        elif gate["name"] == "CY":
            _proc_control_flips(comp, gate)
            comp.add_gate({"name": "S", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            comp.add_gate({"name": "Sdag", "targets": gate["targets"]})
            _proc_control_flips(comp, gate)

        elif gate["name"] == "CZ":
            _proc_control_flips(comp, gate)
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            _proc_control_flips(comp, gate)

        elif gate["name"] == "RX":
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": gate["angle"]}
            )
            comp.add_gate({"name": "H", "targets": gate["targets"]})

        elif gate["name"] == "RY":
            comp.add_gate({"name": "S", "targets": gate["targets"]})
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": gate["angle"]}
            )
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate({"name": "Sdag", "targets": gate["targets"]})

        elif gate["name"] == "CRX":
            _proc_control_flips(comp, gate)
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": gate["angle"] / 2}
            )
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": -gate["angle"] / 2}
            )
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            _proc_control_flips(comp, gate)

        elif gate["name"] == "CRY":
            _proc_control_flips(comp, gate)
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate({"name": "Sdag", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": gate["angle"] / 2}
            )
            comp.add_gate({"name": "S", "targets": gate["targets"]})
            comp.add_gate({"name": "H", "targets": gate["targets"]})

            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )

            comp.add_gate({"name": "H", "targets": gate["targets"]})
            comp.add_gate({"name": "Sdag", "targets": gate["targets"]})
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": -gate["angle"] / 2}
            )
            comp.add_gate({"name": "S", "targets": gate["targets"]})
            comp.add_gate({"name": "H", "targets": gate["targets"]})

            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            _proc_control_flips(comp, gate)

        elif gate["name"] == "CRZ":
            _proc_control_flips(comp, gate)
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": gate["angle"] / 2}
            )
            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            comp.add_gate(
                {"name": "RZ", "targets": gate["targets"], "angle": -gate["angle"] / 2}
            )
            comp.add_gate(
                {"name": "CX", "targets": gate["targets"], "controls": gate["controls"]}
            )
            _proc_control_flips(comp, gate)

        elif gate["name"] == "CCX":
            _proc_control_flips(comp, gate)
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            _add_CCZ(comp, gate)
            comp.add_gate({"name": "H", "targets": gate["targets"]})
            _proc_control_flips(comp, gate)

        elif gate["name"] == "CCZ":
            _add_CCZ(comp, gate)

        elif gate["name"] == "barrier":
            pass

        else:
            comp.add_gate(gate)
    return comp


def verify_decompose_control(circuit):
    gate_list = (
        ["Init0", "MeasZ", "MeasX", "H", "X", "S", "Sdag", "T", "Tdag"]
        + ["CX"]
        + ["RZ"]
    )
    for gate in circuit.gates:
        assert gate["name"] in gate_list
        assert "name" in gate
        assert "targets" in gate
        assert isinstance(gate["targets"], list)
        assert gate["name"] in gate_list
        if gate["name"] in [
            "Init0",
            "MeasZ",
            "MeasX",
            "H",
            "X",
            "S",
            "Sdag",
            "T",
            "Tdag",
        ]:
            assert len(gate["targets"]) == 1
        if gate["name"] in ["RZ"]:
            assert len(gate["targets"]) == 1
            assert "angle" in gate
        if gate["name"] in ["CX"]:
            assert len(gate["targets"]) == 1
            assert len(gate["controls"]) == 1


def count_decompose_control(circuit: Circuit):
    qubit_set = set()
    num_rot = 0
    num_T = 0
    for gate in circuit.gates:
        # print(gate)
        for name in gate["targets"]:
            qubit_set.add(name)
        if "controls" in gate:
            for name in gate["controls"]:
                qubit_set.add(name)
        if gate["name"] in ["Init0", "MeasZ", "MeasX", "H", "X", "S", "Sdag"]:
            pass
        if gate["name"] in ["T", "Tdag"]:
            num_T += 1
        if gate["name"] in ["RZ"]:
            num_rot += 1

    qubits = list(sorted(list(qubit_set)))
    dic = {
        "num_qubit": len(qubit_set),
        "gate_count": len(circuit.gates),
        "num_rot": num_rot,
        "num_T": num_T,
        "qubits": qubits,
        "circuit": circuit.gates,
    }
    return dic
