import numpy as np
from .util import padding_hamiltonian_term, padding_hamiltonian_term_blocked


def Heisenberg_2D_order(lattice: int, split: int, seed: int = 42):
    # number of digit to estimate
    assert lattice % split == 0
    state = np.random.RandomState(seed=seed)
    num_ham_qubit = lattice**2
    num_block = split**2
    num_qubit_per_block = (lattice // split) ** 2
    ham_pauli_list = [[] for _ in range(num_block)]
    for bidx in range(num_block):
        bx = bidx % split
        by = bidx // split
        for idx in range(num_qubit_per_block):
            ix = idx % (lattice // split)
            iy = idx // (lattice // split)
            x = bx * (lattice // split) + ix
            y = by * (lattice // split) + iy
            for dif in ((1, 0), (0, 1)):
                nx = (x + dif[0]) % lattice
                ny = (y + dif[1]) % lattice
                oidx = y * lattice + x
                nidx = ny * lattice + nx
                for pauli in ["X", "Y", "Z"]:
                    # coef = state.randn()
                    coef = 1.0
                    ham_pauli_list[bidx].append((coef, [(oidx, pauli), (nidx, pauli)]))

    all_pauli_list = padding_hamiltonian_term_blocked(ham_pauli_list, num_block)
    return num_ham_qubit, all_pauli_list


def Heisenberg_2D(lattice: int, seed: int = 42):
    # number of digit to estimate
    state = np.random.RandomState(seed=seed)
    num_ham_qubit = lattice * lattice
    ham_pauli_list = []
    for idx in range(num_ham_qubit):
        x = idx % lattice
        y = idx // lattice
        for dif in ((1, 0), (0, 1)):
            nx = (x + dif[0]) % lattice
            ny = (y + dif[1]) % lattice
            nidx = ny * lattice + nx
            for pauli in ["X", "Y", "Z"]:
                # coef = state.randn()
                coef = 1.0
                ham_pauli_list.append((coef, [(idx, pauli), (nidx, pauli)]))

    ham_pauli_list = padding_hamiltonian_term(ham_pauli_list)
    return num_ham_qubit, ham_pauli_list
