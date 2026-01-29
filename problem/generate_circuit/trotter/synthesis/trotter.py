import random
from typing import Dict, List, Tuple

PauliTerm = Tuple[float, List[Tuple[int, str]]]
import numpy as np


def Trotter1st_randomized(
    ham: dict, dt: float, epsilon: float, compress_redundant: bool = True
) -> List[Dict]:
    pos = ham["pos"]
    paulis = ham["pauli"]

    assert len(paulis) > 0
    random.seed(0)  # For reproducibility
    shuffled_paulis = random.sample(paulis, len(paulis))  # shuffle (not in-place)

    num_system = ham["num_qubit"]

    def to_str(tup):
        return "_".join(map(str, tup))

    reg_system = [f"system_{to_str(pos[idx])}" for idx in range(num_system)]

    my_circuit = []
    parallel_pauli_groups_randomized = group_paulis_greedy_no_overlap(shuffled_paulis)
    for pauli_group in parallel_pauli_groups_randomized:
        add_parallel_pauli_rotations_synthesized(
            my_circuit, reg_system, pauli_group, dt, epsilon
        )
    # add_all_pauli_rotations(my_circuit, reg_system, shuffled_paulis, dt)

    if compress_redundant:
        my_circuit = compress_circuit(my_circuit)
    return my_circuit


def Trotter1st(
    ham: dict, dt: float, epsilon: float, compress_redundant: bool = True
) -> List[Dict]:
    """
    Synthesize the circuit to include CX, CY, CZ, RZ.
    """
    pos = ham["pos"]  # List of tuples (x, y, ...) for each qubit
    # paulis = ham["pauli"]  # List of tuples (coeff, [(index, pauli), ...])
    num_system = ham["num_qubit"]

    def to_str(tup):
        return "_".join(map(str, tup))

    reg_system = [f"system_{to_str(pos[idx])}" for idx in range(num_system)]

    my_circuit = []
    parallel_pauli_groups = group_paulis_greedy_no_overlap(ham["pauli"])
    # add_all_pauli_rotations(my_circuit, reg_system, paulis, dt)
    for pauli_group in parallel_pauli_groups:
        add_parallel_pauli_rotations_synthesized(
            my_circuit, reg_system, pauli_group, dt, epsilon
        )

    if compress_redundant:
        my_circuit = compress_circuit(my_circuit)

    return my_circuit


def add_parallel_pauli_rotations_synthesized(
    my_circuit: List[Dict],
    reg_system: List[str],
    parallel_paulis: list,
    dt: float,
    epsilon: float,
) -> None:
    parallel_targets = []
    angles = []
    for pauli in parallel_paulis:
        coeff = pauli[0].real
        pauli_args = pauli[1]
        ind_rot_target, pauli_rot_target = pauli_args[0]

        if pauli_rot_target == "Z":
            my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})
        elif pauli_rot_target == "Y":
            my_circuit.append({"name": "Sdag", "targets": [reg_system[ind_rot_target]]})

        # multi pauli rotation to single pauli rotation
        for ind, p in pauli_args[1:]:
            if p == "X":
                my_circuit.append(
                    {
                        "name": "CX",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Y":
                my_circuit.append(
                    {
                        "name": "CY",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Z":
                my_circuit.append(
                    {
                        "name": "CZ",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )

        # RX gate on my_circuit
        # angle is + dt * coeff, not -dt * coeff, because of Ross-Selinger
        my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})
        parallel_targets.append(ind_rot_target)
        angles.append(+dt * coeff)

    add_parallel_RZ_synthesized(
        my_circuit, parallel_targets, reg_system, angles, epsilon
    )

    for pauli in parallel_paulis:
        coeff = pauli[0]
        pauli_args = pauli[1]
        ind_rot_target, pauli_rot_target = pauli_args[0]

        my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})

        # multi pauli rotation to single pauli rotation
        for ind, p in pauli_args[1:][::-1]:
            if p == "X":
                my_circuit.append(
                    {
                        "name": "CX",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Y":
                my_circuit.append(
                    {
                        "name": "CY",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Z":
                my_circuit.append(
                    {
                        "name": "CZ",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )

        if pauli_rot_target == "Z":
            my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})
        elif pauli_rot_target == "Y":
            my_circuit.append({"name": "S", "targets": [reg_system[ind_rot_target]]})


def add_parallel_RZ_synthesized(
    my_circuit: List[Dict],
    parallel_targets: List[int],
    reg_system: List[str],
    angles: List[float],
    epsilon: float,
) -> None:
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates

    mpmath.mp.dps = 128

    cache = {}
    all_rz_gates = []
    for target, angle in zip(parallel_targets, angles):
        if angle == np.pi/4:
            # this is T gate, since exp(-i (-theta) Z/ 2) is synthesized
            all_rz_gates.append("T")
        elif angle == -np.pi/4:
            all_rz_gates.append("SSST")
        elif angle == 3 * np.pi/4:
            all_rz_gates.append("ST")
        elif angle in [5 * np.pi/4, -3*np.pi/4]:
            all_rz_gates.append("SST")

        if (angle, epsilon) in cache:
            rz_gates = cache[(angle, epsilon)]
        else:
            rz_gates = gridsynth_gates(theta=-angle, epsilon=epsilon)
            cache[(angle, epsilon)] = rz_gates

        all_rz_gates.append(rz_gates)

    longest = max([len(rz_gates) for rz_gates in all_rz_gates])
    for gate_id in range(longest):
        for idx, target in enumerate(parallel_targets):
            if gate_id < len(all_rz_gates[idx]):
                gate = all_rz_gates[idx][gate_id]
                if gate == "H":
                    my_circuit.append({"name": "H", "targets": [reg_system[target]]})
                elif gate == "S":
                    my_circuit.append({"name": "S", "targets": [reg_system[target]]})
                elif gate == "T":
                    my_circuit.append({"name": "T", "targets": [reg_system[target]]})


def add_all_pauli_rotations(
    my_circuit: List[Dict], reg_system: List[str], paulis: list, dt: float
) -> None:
    for pauli in paulis:
        coeff = pauli[0]
        pauli_args = pauli[1]

        ind_rot_target, pauli_rot_target = pauli_args[0]

        if pauli_rot_target == "Z":
            my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})
        elif pauli_rot_target == "Y":
            my_circuit.append({"name": "Sdag", "targets": [reg_system[ind_rot_target]]})

        # multi pauli rotation to single pauli rotation
        for ind, p in pauli_args[1:]:
            if p == "X":
                my_circuit.append(
                    {
                        "name": "CX",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Y":
                my_circuit.append(
                    {
                        "name": "CY",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Z":
                my_circuit.append(
                    {
                        "name": "CZ",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )

        # RX gate on my_circuit
        # angle is + dt * coeff, not -dt * coeff, because of Ross--Selinger
        my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})
        my_circuit.append(
            {
                "name": "RZ",
                "targets": [reg_system[ind_rot_target]],
                "angle": +dt * coeff,
            }
        )
        my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})

        # multi pauli rotation to single pauli rotation
        for ind, p in pauli_args[1:][::-1]:
            if p == "X":
                my_circuit.append(
                    {
                        "name": "CX",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Y":
                my_circuit.append(
                    {
                        "name": "CY",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )
            if p == "Z":
                my_circuit.append(
                    {
                        "name": "CZ",
                        "targets": [reg_system[ind]],
                        "controls": [reg_system[ind_rot_target]],
                    }
                )

        if pauli_rot_target == "Z":
            my_circuit.append({"name": "H", "targets": [reg_system[ind_rot_target]]})
        elif pauli_rot_target == "Y":
            my_circuit.append({"name": "S", "targets": [reg_system[ind_rot_target]]})


def get_support(term: tuple) -> set:
    """Get the set of qubit indices where the Pauli operator acts non-trivially."""
    _, ops = term
    return set(pos for pos, _ in ops)


def group_paulis_greedy_no_overlap(paulis: list) -> list:
    groups = []  # 各グループには PauliTerm のリスト
    group_supports = []  # 各グループの support の集合

    for term in paulis:
        supp = get_support(term)
        placed = False

        for i, support in enumerate(group_supports):
            if supp.isdisjoint(support):  # 重複がないなら追加
                groups[i].append(term)
                group_supports[i].update(supp)
                placed = True
                break

        if not placed:
            groups.append([term])
            group_supports.append(set(supp))

    return groups


def is_inverse(gate1: Dict, gate2: Dict) -> bool:
    """2つのゲートが互いに打ち消し合う(=恒等になる)かどうかを判定"""
    # if gate1['name'] != gate2['name']:
    # return False

    # targets, controlsの順序に依存しない比較
    targets1 = set(gate1.get("targets", []))
    targets2 = set(gate2.get("targets", []))
    if targets1 != targets2:
        return False

    controls1 = set(gate1.get("controls", []))  # デフォルトで空集合
    controls2 = set(gate2.get("controls", []))
    if controls1 != controls2:
        return False

    # Hadamard ゲートは2回で identity
    if gate1["name"] == "H" and gate2["name"] == "H":
        return True
    elif gate1["name"] == "S" and gate2["name"] == "Sdag":
        return True
    elif gate1["name"] == "CX" and gate2["name"] == "CX":
        return True

    elif gate1["name"] == "CY" and gate2["name"] == "CY":
        return True
    elif gate1["name"] == "CZ" and gate2["name"] == "CZ":
        return True

    # RZゲートで角度が等しく逆符号なら消せる（簡単化例）
    if gate1["name"] == "RZ":
        angle1 = gate1.get("note", {}).get("angle")
        angle2 = gate2.get("note", {}).get("angle")
        return angle1 is not None and angle2 is not None and abs(angle1 + angle2) < 1e-8

    # その他のゲートについては必要に応じてルール追加
    return False


def compress_circuit(circuit: List[Dict]) -> List[Dict]:
    """隣接ゲートが互いに打ち消す場合、それらを削除して圧縮"""
    stack = []
    for gate in circuit:
        if stack and is_inverse(stack[-1], gate):
            stack.pop()
        else:
            stack.append(gate)
    return stack
