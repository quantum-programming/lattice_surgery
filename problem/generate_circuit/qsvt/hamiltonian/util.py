import numpy as np


def _from_openfermion_to_list(ham) -> list:
    result = []
    for op in ham:
        for paulis, coef in op.terms.items():
            item = (coef, list(paulis))
            result.append(item)
    return result


def padding_hamiltonian_term(ham_pauli_list: list) -> list:
    term_cnt = len(ham_pauli_list)
    term_cnt_log = int(np.log2(term_cnt - 1e-10)) + 1
    term_cnt_fix = 2**term_cnt_log
    # assert(term_cnt < term_cnt_fix)
    padding = [(0, []) for _ in range(term_cnt_fix - term_cnt)]
    ham_pauli_list.extend(padding)
    return ham_pauli_list


def padding_hamiltonian_term_blocked(ham_pauli_list: list, num_block: int) -> list:
    term_cnt = sum([len(block) for block in ham_pauli_list])
    term_cnt_log = int(np.log2(term_cnt - 1e-10)) + 1
    term_cnt_fix = 2**term_cnt_log
    assert term_cnt < term_cnt_fix
    padding_cnt = term_cnt_fix - term_cnt
    padding_cnt_block = padding_cnt // num_block
    residual = padding_cnt % num_block
    for bidx in range(num_block):
        if bidx < residual:
            padding = [(0, []) for _ in range(padding_cnt_block + 1)]
        else:
            padding = [(0, []) for _ in range(padding_cnt_block)]
        ham_pauli_list[bidx].extend(padding)

    all_pauli_list = []
    for block in ham_pauli_list:
        all_pauli_list.extend(block)

    # print(all_pauli_list, padding_cnt, padding_cnt_block, residual, len(all_pauli_list), term_cnt_fix)
    assert len(all_pauli_list) == term_cnt_fix
    return all_pauli_list


def padding_hamiltonian_term_thread(ham_pauli_list: list, num_block: int) -> list:
    ham_pauli_list_blocked = []
    num_term = len(ham_pauli_list)
    base = num_term // num_block
    residual = num_term % num_block
    for ind in range(num_block):
        start = ind * base + min(ind, residual)
        end = (ind + 1) * base + min(ind + 1, residual)
        ham_pauli_list_blocked.append(ham_pauli_list[start:end])

    raw_block_size = max([len(block) for block in ham_pauli_list_blocked])
    assert raw_block_size != 0
    if raw_block_size == 1:
        fix_block_log = 0
    else:
        fix_block_log = int(np.log2(raw_block_size - 1e-10)) + 1
    fix_block_size = 2**fix_block_log
    # print(fix_block_size, "*"*10, raw_block_size, fix_block_log)
    for bidx in range(len(ham_pauli_list_blocked)):
        res = fix_block_size - len(ham_pauli_list_blocked[bidx])
        assert res >= 0
        ham_pauli_list_blocked[bidx].extend([(0, []) for _ in range(res)])
    all_pauli_list = []
    for block in ham_pauli_list_blocked:
        all_pauli_list.extend(block)
    return all_pauli_list
