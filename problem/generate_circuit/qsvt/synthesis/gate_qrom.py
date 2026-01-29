from __future__ import annotations

from typing import Union

from .circuit import Circuit


def add_X(c: Circuit, tgt: str):
    c.add_gate({"name": "X", "targets": [tgt]})


def add_RX(c: Circuit, tgt: str, angle: float):
    c.add_gate({"name": "RX", "targets": [tgt], "angle": angle})


def add_RY(c: Circuit, tgt: str, angle: float):
    c.add_gate({"name": "RY", "targets": [tgt], "angle": angle})


def add_RZ(c: Circuit, tgt: str, angle: float):
    c.add_gate({"name": "RZ", "targets": [tgt], "angle": angle})


def add_CX(c: Circuit, ctl: str, tgt: str, c1: int = 1):
    if ctl is None:
        add_X(c, tgt)
    else:
        c.add_gate(
            {"name": "CX", "controls": [ctl], "targets": [tgt], "control_flips": [c1]}
        )


def add_CY(c: Circuit, ctl: str, tgt: str):
    c.add_gate({"name": "CY", "controls": [ctl], "targets": [tgt]})


def add_CZ(c: Circuit, ctl: str, tgt: str):
    c.add_gate({"name": "CZ", "controls": [ctl], "targets": [tgt]})


def add_CRX(c: Circuit, ctl: str, tgt: str, angle: float):
    if ctl is None:
        add_RX(c, tgt)
    else:
        c.add_gate({"name": "CRX", "controls": [ctl], "targets": [tgt], "angle": angle})


def add_CRY(c: Circuit, ctl: str, tgt: str, angle: float):
    c.add_gate({"name": "CRY", "controls": [ctl], "targets": [tgt], "angle": angle})


def add_CRZ(c: Circuit, ctl: str, tgt: str, angle: float):
    c.add_gate({"name": "CRZ", "controls": [ctl], "targets": [tgt], "angle": angle})


def add_toffoli(circuit: Circuit, t1: int, t2: int, t3: int, c1: int, c2: int) -> None:
    circuit.add_gate(
        {
            "name": "MCX",
            "controls": [t1, t2],
            "control_flips": [c1, c2],
            "targets": [t3],
        }
    )


def add_start_toffoli(
    circuit: Circuit, t1: int, t2: int, t3: int, c1: int, c2: int
) -> None:
    assert t1 is not None and t3 is not None
    if t2 is None:
        add_CX(circuit, t1, t3, c1)
    else:
        circuit.add_gate(
            {
                "name": "CCX",
                "controls": [t1, t2],
                "control_flips": [c1, c2],
                "targets": [t3],
                "note": "start_t3",
            }
        )


def add_end_toffoli(
    circuit: Circuit, t1: int, t2: int, t3: int, c1: int, c2: int
) -> None:
    assert t1 is not None and t3 is not None
    if t2 is None:
        add_CX(circuit, t1, t3, c1)
    else:
        circuit.add_gate(
            {
                "name": "CCX",
                "controls": [t1, t2],
                "control_flips": [c1, c2],
                "targets": [t3],
                "note": "end_t3",
            }
        )


def create_control_qrom_simple(
    c: Circuit,
    control: list[str],
    target: list[str],
    ancilla: list[str],
    gcnt: Union[str, None],
    pauli_list: list[tuple[float, tuple]],
) -> Circuit:
    """Add QROM to registers

    Args:
        c (Circuit): Quantum Circuit
        control (list): control registers
        target (list): target registers
        ancilla (list): ancilla registers
        val (int, optional): _description_. Defaults to 0.
        pauli_list (list): _description_

    Returns:
        Circuit: _description_
    """
    assert len(control) == len(ancilla)

    num_control = len(control)
    control = [f"{c}_th_0" for c in control]

    fix_anc = [gcnt] + ancilla
    fix_anc = [f"{c}_th_0" if c is not None else None for c in fix_anc]
    accum = fix_anc[-1]

    for step in range(2**num_control):
        check = step
        vals = []
        for ind in range(num_control):
            vals.append(check % 2)
            check = check >> 1
        vals = list(reversed(vals))

        # c.add_gate({"name": "barrier", "targets": []})
        for ind in range(num_control):
            # print(f"c{ind}, a{ind}, a{ind+1}")
            add_start_toffoli(
                c, control[ind], fix_anc[ind], fix_anc[ind + 1], vals[ind], 1
            )
        # c.add_gate({"name": "barrier", "targets": []})
        for pauli in pauli_list[step][1]:
            target_idx = pauli[0]
            target_pauli = pauli[1]
            if target_pauli == "X":
                add_CX(c, accum, target[target_idx])
            if target_pauli == "Y":
                add_CY(c, accum, target[target_idx])
            if target_pauli == "Z":
                add_CZ(c, accum, target[target_idx])
            # print(f"a{len(fix_anc)-1}, t{target_idx}")
        c.add_gate({"name": "barrier", "targets": []})
        for ind in range(num_control - 1, -1, -1):
            add_end_toffoli(
                c, control[ind], fix_anc[ind], fix_anc[ind + 1], vals[ind], 1
            )


def create_control_qrom_sawtooth(
    c: Circuit,
    control: list[str],
    target: list[str],
    ancilla: list[str],
    gcnt: Union[str, None],
    pauli_list: list[tuple[float, tuple]],
) -> Circuit:
    """Add QROM to registers

    Args:
        c (Circuit): Quantum Circuit
        control (list): control registers
        target (list): target registers
        ancilla (list): ancilla registers
        val (int, optional): _description_. Defaults to 0.
        pauli_list (list): _description_

    Returns:
        Circuit: _description_
    """
    assert len(control) == len(ancilla)

    """
    add_X(c, 0)
    for ind in range(control):
        if val%2==1:
            add_X(c, 1+ind*2)
        val//=2
    # circuit.barrier()
    """
    num_control = len(control)
    control = [f"{c}_th_0" for c in control]

    fix_anc = [gcnt] + ancilla
    fix_anc = [f"{c}_th_0" if c is not None else None for c in fix_anc]
    accum = fix_anc[-1]

    for ind in range(num_control):
        # print(f"c{ind}, a{ind}, a{ind+1}")
        add_start_toffoli(c, control[ind], fix_anc[ind], fix_anc[ind + 1], 0, 1)

    cur = num_control
    for step in range(2**num_control):
        for pauli in pauli_list[step][1]:
            target_idx = pauli[0]
            target_pauli = pauli[1]
            if target_pauli == "X":
                add_CX(c, accum, target[target_idx])
            if target_pauli == "Y":
                add_CY(c, accum, target[target_idx])
            if target_pauli == "Z":
                add_CZ(c, accum, target[target_idx])
            # print(f"a{len(fix_anc)-1}, t{target_idx}")
        rev = 0
        step_sub = step
        while step_sub % 2 != 0:
            step_sub //= 2
            rev += 1
        # print(step, rev)
        for ind in range(rev):
            # print(f"c{cur-1}, a{cur-1}, a{cur}")
            add_end_toffoli(c, control[cur - 1], fix_anc[cur - 1], fix_anc[cur], 1, 1)
            cur -= 1
        if step + 1 == 2**num_control:
            break
        # print(f"a{cur-1}, a{cur}")
        add_CX(c, fix_anc[cur - 1], fix_anc[cur])
        for ind in range(rev):
            # print(f"c{cur}, a{cur}, a{cur+1}")
            add_start_toffoli(c, control[cur], fix_anc[cur], fix_anc[cur + 1], 0, 1)
            cur += 1


def _get_bits(val, num_digit):
    check = val
    vals = []
    for ind in range(num_digit):
        vals.append(check % 2)
        check = check >> 1
    vals = list(reversed(vals))
    return vals


def create_control_qrom_dist_improve(
    c: Circuit,
    control: list[str],
    target: list[str],
    ancilla: list[str],
    gcnt: Union[str, None],
    pauli_list: list[tuple[float, tuple]],
    num_dup: int,
) -> Circuit:
    """Add QROM to registers

    Args:
        c (Circuit): Quantum Circuit
        control (list): control registers
        target (list): target registers
        ancilla (list): ancilla registers
        val (int, optional): _description_. Defaults to 0.
        pauli_list (list): _description_

    Returns:
        Circuit: _description_
    """
    assert len(control) == len(ancilla)

    num_control = len(control)
    dups = [[f"{c}_th_0" for c in control]] + [
        [f"{c}_th_{d + 1}" for c in control] for d in range(2**num_dup - 1)
    ]
    # print(dups)

    # duplicate
    for ind in range(num_dup):
        for a in range(2**ind):
            for ci in range(num_control):
                # print(dups[a][ci], dups[a+2**ind][ci])
                add_CX(c, dups[a][ci], dups[a + 2**ind][ci])

    fix_anc_org = [gcnt] + ancilla
    fix_ancs = [[f"{c}_th_0" if c is not None else None for c in fix_anc_org]] + [
        [f"{c}_th_{d + 1}" if c is not None else None for c in fix_anc_org]
        for d in range(2**num_dup - 1)
    ]
    accums = [reg[-1] for reg in fix_ancs]
    num_control = len(control)

    if 0:
        for ind in range(num_dup):
            for di in range(2**num_dup):
                dits = _get_bits(di, num_dup)
                add_start_toffoli(
                    c,
                    dups[di][ind],
                    fix_ancs[di][ind],
                    fix_ancs[di][ind + 1],
                    dits[ind],
                    1,
                )
            c.add_gate({"name": "barrier", "targets": []})

    if 1:
        for ind in range(num_dup):
            for di in range(2 ** (ind + 1)):
                dits = _get_bits(di, ind + 1)
                div = 2 ** (num_dup - ind - 1)
                add_start_toffoli(
                    c,
                    dups[di * div][ind],
                    fix_ancs[di * div][ind],
                    fix_ancs[di * div][ind + 1],
                    dits[ind],
                    1,
                )
                if ind + 1 < num_dup:
                    add_CX(
                        c,
                        fix_ancs[di * div][ind + 1],
                        fix_ancs[di * div + div // 2][ind + 1],
                    )
            c.add_gate({"name": "barrier", "targets": []})

    for ind in range(num_dup, num_control):
        for di in range(2**num_dup):
            add_start_toffoli(
                c, dups[di][ind], fix_ancs[di][ind], fix_ancs[di][ind + 1], 0, 1
            )

    cur = num_control

    for step in range(2 ** (num_control - num_dup)):
        # c.add_gate({"name": "barrier", "targets": []})

        flag = True
        pi = 0
        while flag:
            flag = False
            for di in range(2**num_dup):
                if pi >= len(pauli_list[di * (2 ** (num_control - num_dup)) + step][1]):
                    continue
                pauli = pauli_list[di * (2 ** (num_control - num_dup)) + step][1][pi]
                flag = True
                target_idx = pauli[0]
                target_pauli = pauli[1]
                if target_pauli == "X":
                    add_CX(c, accums[di], target[target_idx])
                if target_pauli == "Y":
                    add_CY(c, accums[di], target[target_idx])
                if target_pauli == "Z":
                    add_CZ(c, accums[di], target[target_idx])
                # print(f"a{len(fix_anc)-1}, t{target_idx}")
            pi += 1

        rev = 0
        step_sub = step
        while step_sub % 2 != 0:
            step_sub //= 2
            rev += 1
        # print(step, rev)
        c.add_gate({"name": "barrier", "targets": []})
        for ind in range(rev):
            # print(f"c{cur-1}, a{cur-1}, a{cur}")
            for di in range(2**num_dup):
                add_end_toffoli(
                    c, dups[di][cur - 1], fix_ancs[di][cur - 1], fix_ancs[di][cur], 1, 1
                )
            cur -= 1
        if step + 1 == 2 ** (num_control - num_dup):
            break
        # print(f"a{cur-1}, a{cur}")
        # c.add_gate({"name": "barrier", "targets": []})
        for di in range(2**num_dup):
            # print(fix_ancs[di][cur-1],cur)
            add_CX(c, fix_ancs[di][cur - 1], fix_ancs[di][cur])
        # c.add_gate({"name": "barrier", "targets": []})
        for ind in range(rev):
            # print(f"c{cur}, a{cur}, a{cur+1}")
            for di in range(2**num_dup):
                add_start_toffoli(
                    c, dups[di][cur], fix_ancs[di][cur], fix_ancs[di][cur + 1], 0, 1
                )
            cur += 1

    if 0:
        # c.add_gate({"name": "barrier", "targets": []})
        for ind in range(num_dup - 1, -1, -1):
            for di in range(2**num_dup):
                dits = _get_bits(di, num_dup)
                add_end_toffoli(
                    c,
                    dups[di][ind],
                    fix_ancs[di][ind],
                    fix_ancs[di][ind + 1],
                    dits[ind],
                    1,
                )
    if 1:
        for ind in range(num_dup - 1, -1, -1):
            for di in range(2 ** (ind + 1) - 1, -1, -1):
                dits = _get_bits(di, ind + 1)
                div = 2 ** (num_dup - ind - 1)
                if ind + 1 < num_dup:
                    add_CX(
                        c,
                        fix_ancs[di * div][ind + 1],
                        fix_ancs[di * div + div // 2][ind + 1],
                    )
                add_start_toffoli(
                    c,
                    dups[di * div][ind],
                    fix_ancs[di * div][ind],
                    fix_ancs[di * div][ind + 1],
                    dits[ind],
                    1,
                )
            c.add_gate({"name": "barrier", "targets": []})

    # uncompute
    # c.add_gate({"name": "barrier", "targets": []})
    for ind in range(num_dup - 1, -1, -1):
        for a in range(2**ind):
            for ci in range(num_control):
                add_CX(c, dups[a][ci], dups[a + 2**ind][ci])


def create_control_qrom_dist_improve_earlydrop(
    c: Circuit,
    control: list[str],
    target: list[str],
    ancilla: list[str],
    gcnt: Union[str, None],
    pauli_list: list[tuple[float, tuple]],
    num_dup: int,
) -> Circuit:
    """Add QROM to registers

    Args:
        c (Circuit): Quantum Circuit
        control (list): control registers
        target (list): target registers
        ancilla (list): ancilla registers
        val (int, optional): _description_. Defaults to 0.
        pauli_list (list): _description_

    Returns:
        Circuit: _description_
    """
    assert len(control) == len(ancilla)
    _debug_cnt = 0

    num_control = len(control)
    dups = [[f"{c}_th_0" for c in control]] + [
        [f"{c}_th_{d + 1}" for c in control] for d in range(2**num_dup - 1)
    ]

    # copy parent index to children
    for ind in range(num_dup):
        for a in range(2**ind):
            for ci in range(num_control):
                # print(dups[a][ci], dups[a+2**ind][ci])
                add_CX(c, dups[a][ci], dups[a + 2**ind][ci])

    # create copies of ancilla
    fix_anc_org = [gcnt] + ancilla
    fix_ancs = [[f"{c}_th_0" if c is not None else None for c in fix_anc_org]] + [
        [f"{c}_th_{d + 1}" if c is not None else None for c in fix_anc_org]
        for d in range(2**num_dup - 1)
    ]
    accums = [reg[-1] for reg in fix_ancs]
    num_control = len(control)

    # create AND of top num_dup bits
    #  with sharing the common ancilla
    for ind in range(num_dup):
        for di in range(2 ** (ind + 1)):
            dits = _get_bits(di, ind + 1)
            div = 2 ** (num_dup - ind - 1)
            add_start_toffoli(
                c,
                dups[di * div][ind],
                fix_ancs[di * div][ind],
                fix_ancs[di * div][ind + 1],
                dits[ind],
                1,
            )
            if ind + 1 < num_dup:
                add_CX(
                    c,
                    fix_ancs[di * div][ind + 1],
                    fix_ancs[di * div + div // 2][ind + 1],
                )

    block_size = 2 ** (num_control - num_dup)
    num_threads = 2**num_dup

    # iterate first Toffoli, create AND of lower (num_control - num_dup) bits
    for ind in range(num_dup, num_control):
        for di in range(num_threads):
            add_start_toffoli(
                c, dups[di][ind], fix_ancs[di][ind], fix_ancs[di][ind + 1], 0, 1
            )

    cur = num_control
    # c.add_gate({"name": "barrier", "targets": []})
    for step in range(block_size):
        # apply control-Pauli
        pauli_index = 0
        finish_flag = [False] * num_threads

        for thread_index in range(num_threads):
            if len(pauli_list[thread_index * block_size + step][1]) > 0:
                _debug_cnt += 1

        while not all(finish_flag):
            # loop for all threads
            for thread_index in range(num_threads):
                # if already finish, skip
                if finish_flag[thread_index]:
                    continue

                pauli_single_terms = pauli_list[thread_index * block_size + step][1]
                # if pauli string is end, finish and skip
                if pauli_index >= len(pauli_single_terms):
                    finish_flag[thread_index] = True
                    continue

                pauli = pauli_single_terms[pauli_index]
                target_idx = pauli[0]
                target_pauli = pauli[1]
                if target_pauli == "X":
                    add_CX(c, accums[thread_index], target[target_idx])
                elif target_pauli == "Y":
                    add_CY(c, accums[thread_index], target[target_idx])
                elif target_pauli == "Z":
                    add_CZ(c, accums[thread_index], target[target_idx])
                else:
                    assert False
            pauli_index += 1
        c.add_gate({"name": "barrier", "targets": []})

        # calculate number of back and progress bit
        revert_bit = 0
        step_sub = step
        while step_sub % 2 != 0:
            step_sub //= 2
            revert_bit += 1
        # print(step, revert_bit)

        # cancel AND of lower bits
        for _ in range(revert_bit):
            # print(f"c{cur-1}, a{cur-1}, a{cur}")
            for thread_index in range(num_threads):
                add_end_toffoli(
                    c,
                    dups[thread_index][cur - 1],
                    fix_ancs[thread_index][cur - 1],
                    fix_ancs[thread_index][cur],
                    1,
                    1,
                )
            cur -= 1

        # finishe if this is the last iteration
        if step + 1 == 2 ** (num_control - num_dup):
            break
        # print(f"a{cur-1}, a{cur}")
        # c.add_gate({"name": "barrier", "targets": []})

        # check all threads finish in intermediate, revert all
        finish_flag = [False] * num_threads
        for thread_index in range(num_threads):
            term = pauli_list[thread_index * block_size + step + 1]
            # padding term
            if term == (0, []):
                finish_flag[thread_index] = True
                # print("DROP", thread_index, step)
        if all(finish_flag):
            # print("DROP success")
            # print(f"retire at step {step}")
            dits = _get_bits(step, num_control - num_dup)
            for ind in range(num_dup, num_control - revert_bit):
                for thread_index in range(num_threads):
                    # print(dits, dits[num_control-num_dup-revert_bit-(ind-num_dup)-1])
                    add_end_toffoli(
                        c,
                        dups[thread_index][cur - 1],
                        fix_ancs[thread_index][cur - 1],
                        fix_ancs[thread_index][cur],
                        dits[num_control - revert_bit - ind - 1],
                        1,
                    )
                cur -= 1
            break

        # perform CNOT to flip a bit
        for thread_index in range(2**num_dup):
            # print(fix_ancs[thread_index][cur-1],cur)
            add_CX(c, fix_ancs[thread_index][cur - 1], fix_ancs[thread_index][cur])
        # c.add_gate({"name": "barrier", "targets": []})

        # re-create the loewr bits
        for _ in range(revert_bit):
            # print(f"c{cur}, a{cur}, a{cur+1}")
            for thread_index in range(2**num_dup):
                add_start_toffoli(
                    c,
                    dups[thread_index][cur],
                    fix_ancs[thread_index][cur],
                    fix_ancs[thread_index][cur + 1],
                    0,
                    1,
                )
            cur += 1

    # uncompute shared index
    for ind in range(num_dup - 1, -1, -1):
        for thread_index in range(2 ** (ind + 1) - 1, -1, -1):
            dits = _get_bits(thread_index, ind + 1)
            div = 2 ** (num_dup - ind - 1)
            if ind + 1 < num_dup:
                add_CX(
                    c,
                    fix_ancs[thread_index * div][ind + 1],
                    fix_ancs[thread_index * div + div // 2][ind + 1],
                )
            add_start_toffoli(
                c,
                dups[thread_index * div][ind],
                fix_ancs[thread_index * div][ind],
                fix_ancs[thread_index * div][ind + 1],
                dits[ind],
                1,
            )
        c.add_gate({"name": "barrier", "targets": []})
    # c.add_gate({"name": "barrier", "targets": []})

    # uncompute all
    for ind in range(num_dup - 1, -1, -1):
        for a in range(2**ind):
            for ci in range(num_control):
                add_CX(c, dups[a][ci], dups[a + 2**ind][ci])

    # check all iterated
    valid_cnt = len([term for term in pauli_list if term != (0, [])])
    if valid_cnt != _debug_cnt:
        print(valid_cnt, _debug_cnt)
        assert valid_cnt == _debug_cnt


def test_qrom_drop(num_control, num_dups, num_task, mode, verbose=False):
    c = Circuit()
    control = [f"c{idx + 1}" for idx in range(num_control)]
    ancilla = [f"a{idx + 1}" for idx in range(num_control)]
    target = ["t1"]
    num_term = 2**num_control
    import numpy as np

    rvals = np.random.choice([0, 1], size=num_term)
    pauli_list = []
    for ind in range(num_term):
        s = "X" if rvals[ind] else "I"
        pauli_list.append((0.1, [(0, s)]))

    num_threads = 2**num_dups
    block_size = num_term // num_threads
    assert num_threads <= num_term
    assert num_term % block_size == 0
    assert num_task <= block_size
    for step in range(num_task, block_size):
        for thread_index in range(num_threads):
            pauli_list[thread_index * block_size + step] = (0, [])
            rvals[thread_index * block_size + step] = 0
    if verbose:
        print(pauli_list)

    if mode == "simple":
        create_control_qrom_simple(c, control, target, ancilla, None, pauli_list)
    elif mode == "sawtooth":
        create_control_qrom_sawtooth(c, control, target, ancilla, None, pauli_list)
    elif mode == "dist_improve":
        create_control_qrom_dist_improve(
            c, control, target, ancilla, None, pauli_list, num_dups
        )
    elif mode == "dist_earlydrop":
        create_control_qrom_dist_improve_earlydrop(
            c, control, target, ancilla, None, pauli_list, num_dups
        )
    else:
        raise Exception("Unknown mode")

    def print_state(state):
        thread = 0
        st = ""
        while True:
            # print control
            k = [
                s
                for s in state.keys()
                if s.startswith("c") and s.endswith(f"_th_{thread}")
            ]
            if len(k) == 0:
                break
            for c in k:
                st += f"{state[c]}"
            st += ":"
            # print ancilla
            k = [
                s
                for s in state.keys()
                if s.startswith("a") and s.endswith(f"_th_{thread}")
            ]
            for c in k:
                st += f"{state[c]}"
            st += "   "
            thread += 1

        st += str(state["t1"])
        return st

    def check(num_control, rval, init):
        # provide "init" for control part
        # the result should be rval

        from collections import defaultdict

        state = defaultdict(int)

        # store mod-2 integer
        vals = []
        for ind in range(num_control):
            vals.append(init % 2)
            init = init >> 1
        vals = list(reversed(vals))

        # set states
        for ind in range(num_control):
            state[f"c{ind + 1}_th_0"] = vals[ind]

        # simulate circuit
        for gate in c.gates:
            if gate["name"] == "CCX":
                v0 = state[gate["controls"][0]]
                v1 = state[gate["controls"][1]]
                f0 = gate["control_flips"][0]
                f1 = gate["control_flips"][1]
                if v0 == f0 and v1 == f1:
                    state[gate["targets"][0]] ^= 1
                else:
                    state[gate["targets"][0]] = state[gate["targets"][0]]
            if gate["name"] == "CX":
                v0 = state[gate["controls"][0]]
                f0 = gate["control_flips"][0]
                if v0 == f0:
                    state[gate["targets"][0]] ^= 1
                else:
                    state[gate["targets"][0]] = state[gate["targets"][0]]
            if gate["name"] == "X":
                state[gate["targets"][0]] ^= 1
            if gate["name"] == "barrier":
                # print("="*100)
                if verbose:
                    print(print_state(state))
                pass
            # print(gate)

        if verbose:
            print(print_state(state), rval)
        # control must be original value
        for ind in range(num_control):
            assert state[f"c{ind + 1}_th_0"] == vals[ind]
        # ancilla must be uncomputed
        for ind in range(num_control):
            assert state[f"a{ind + 1}_th_0"] == 0
        for name in state.keys():
            if name.startswith("c") and name.endswith("_th_0"):
                continue
            if name == "t1":
                continue
            assert state[name] == 0
        # target must agree with the rval
        assert state["t1"] == rval

    for ind in range(2**num_control):
        # print(rvals)
        check(num_control, rvals[ind], ind)

    cnt = 0
    for gate in c.gates:
        if gate["name"] == "CCX":
            cnt += 1
    print(cnt)


def create_qrot():
    assert False


def create_control_qrom():
    assert False
