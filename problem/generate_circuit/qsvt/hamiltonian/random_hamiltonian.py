
import random
from openfermion.ops import QubitOperator
from .util import _from_openfermion_to_list
from openfermion import count_qubits

def random_hamiltonian(N: int, M: int, seed: int = 1234) -> QubitOperator:
    """
    Generate a random N-qubit Hamiltonian as a sum of M unique non-identity Pauli strings
    with ±1 coefficients.

    Args:
        N (int): Number of qubits.
        M (int): Number of unique Pauli terms (nontrivial, i.e., not all-I).
        seed (int, optional): Random seed. Default is 1234.

    Returns:
        QubitOperator: A Hamiltonian with M random Pauli terms.
    """
    if M > (4**N - 1):  # exclude all-I term
        raise ValueError("M cannot be larger than 4^N - 1 (excluding all-identity term).")
        
    if seed is not None:
        random.seed(seed)
    paulis = ['I', 'X', 'Y', 'Z']
    seen = set()
    terms = []

    while len(terms) < M:
        # Generate a random Pauli string as a tuple
        p_tuple = tuple(random.choices(paulis, k=N))
        if all(p == 'I' for p in p_tuple):  # skip all-I
            continue
        if p_tuple in seen:
            continue
        seen.add(p_tuple)

        # Construct term string like 'X0 Y2'
        term_str = ' '.join(f"{p}{i}" for i, p in enumerate(p_tuple) if p != 'I')
        coeff = random.choice([-1, 1])
        terms.append(QubitOperator(term_str, coeff))

    # Combine into a single QubitOperator
    ham_opf = sum(terms, QubitOperator())
    ham = _from_openfermion_to_list(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1])>0]    

    num_qubits = count_qubits(ham_opf)

    #raise Exception("This function is not implemented yet")
    pos_dict_fix = {}
    for ind in range(num_qubits):
        pos_dict_fix[ind] = (ind, )

    result = {
        "num_qubit": num_qubits,
        "pos": pos_dict_fix,
        "pauli": ham
    }        
    return result



def random_local_hamiltonian(N: int, M: int, k: int, seed: int = 1234) -> QubitOperator:
    """
    Generate a random N-qubit Hamiltonian with M unique Pauli terms,
    each term acting on at most k qubits (k-local), and nontrivial (non-identity).

    Args:
        N (int): Number of qubits.
        M (int): Number of terms in the Hamiltonian.
        k (int): Locality constraint (each term acts nontrivially on ≤ k qubits).
        seed (int, optional): Random seed for reproducibility.

    Returns:
        QubitOperator: The resulting random k-local Hamiltonian.
    """
    if not (1 <= k <= N):
        raise ValueError("k must satisfy 1 <= k <= N")
    
    # Estimate upper bound on number of unique k-local Pauli terms
    # total = sum_{j=1}^{k} (N choose j) * 3^j
    from math import comb
    max_unique_terms = sum(comb(N, j) * (3 ** j) for j in range(1, k+1))
    if M > max_unique_terms:
        raise ValueError(f"M cannot be greater than the number of unique ≤{k}-local Pauli terms.")

    random.seed(seed)
    paulis = ['X', 'Y', 'Z']
    seen = set()
    terms = []

    while len(terms) < M:
        # Randomly choose locality for this term: between 1 and k
        #locality = random.randint(1, k)
        #locality = k
        qubit_indices = sorted(random.sample(range(N), k))

        # Assign a random Pauli (X/Y/Z) to each selected qubit
        term_ops = [(q, random.choice(paulis)) for q in qubit_indices]
        
        # Construct string like 'X0 Z3'
        term_str = ' '.join(f"{p}{i}" for i, p in term_ops)
        key = tuple(sorted(term_ops))  # canonical form for checking uniqueness
        if key in seen:
            continue
        seen.add(key)

        coeff = random.choice([-1, 1])
        terms.append(QubitOperator(term_str, coeff))

    # Combine into a single QubitOperator
    ham_opf = sum(terms, QubitOperator())
    ham = _from_openfermion_to_list(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1])>0]    

    num_qubits = count_qubits(ham_opf)

    #raise Exception("This function is not implemented yet")
    pos_dict_fix = {}
    for ind in range(num_qubits):
        pos_dict_fix[ind] = (ind, )

    result = {
        "num_qubit": num_qubits,
        "pos": pos_dict_fix,
        "pauli": ham
    }        
    return result
