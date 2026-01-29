from openfermion import FermionOperator, count_qubits
from openfermion import jordan_wigner, bravyi_kitaev

from .util import _from_openfermion_to_list


def single_site_single_band(
    N_B_per_orbital: int,
    U: float = 1,
    t: float = 1,
    e_list=None,
    encoding: str = "jordan-wigner",
):
    ham_opf = _single_site_single_band_hamiltonian(
        N_B_per_orbital, U=U, t=t, e_list=e_list, encoding=encoding
    )
    ham = _from_openfermion_to_list(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1]) > 0]

    num_qubits = count_qubits(ham_opf)

    pos_dict_fix = {}
    for spin in range(2):
        ind = spin * (N_B_per_orbital + 1)
        pos_dict_fix[ind] = (0, spin)

        for bath_ind in range(N_B_per_orbital):
            ind = spin * (N_B_per_orbital + 1) + bath_ind
            pos_dict_fix[ind] = (bath_ind + 1, spin)

    result = {"num_qubit": num_qubits, "pos": pos_dict_fix, "pauli": ham}
    return result


def _single_site_single_band_hamiltonian(
    N_B_per_orbital, U=1, t=1, e_list=None, encoding="jordan-wigner", verbose=0
):
    """
    N_B_per_orbital: number of bath sites
    U : repulsion in impurity electron
    """
    n_site = 1
    n_orbital = 2 * n_site
    N_B = N_B_per_orbital * n_orbital
    if e_list is None:
        e_list = [0.5 for i in range(N_B)]

    ham_f = FermionOperator()

    # electronic interaction
    for n in range(n_site):
        ham_f += U * FermionOperator(f"{2*n}^ {2*n} {2*n+1}^ {2*n+1}")

    # impurity-bath hopping
    for j in range(n_orbital):
        imp_index = j * (N_B_per_orbital + 1)
        for i in range(N_B_per_orbital):
            bath_index = imp_index + i + 1

            if verbose:
                print(f"{imp_index=}, {bath_index=}")
            ham_f += t * (
                FermionOperator(f"{imp_index}^ {bath_index}")
                + FermionOperator(f"{bath_index}^ {imp_index}")
            )

    # conduction
    count = 0
    for n in range(n_site):
        for sigma in [0, 1]:
            for m in range(N_B_per_orbital):
                bath_index = 1 + m + (N_B_per_orbital + 1) * (2 * n + sigma)
                ham_f += e_list[count] * FermionOperator(f"{bath_index}^ {bath_index}")

                if verbose:
                    print(f"{count=}, {bath_index=}")

                count += 1

    if encoding == "jordan-wigner":
        encoder = jordan_wigner
    elif encoding == "bravyi-kitaev":
        encoder = bravyi_kitaev
    elif encoding == "fermion":
        encoder = lambda x: x

    return encoder(ham_f)


from openfermion import FermionOperator
from openfermion import jordan_wigner, bravyi_kitaev


def chain_site_single_band(
    n_site,
    N_B_per_orbital: int,
    U: float = 1.0,
    V: float = 1.0,
    t: float = 1.0,
    e_list=None,
    encoding: str = "jordan-wigner",
):
    ham_opf = _chain_site_single_band_hamiltonian(
        n_site, N_B_per_orbital, U=U, V=V, t=t, e_list=e_list, encoding=encoding
    )
    ham = _from_openfermion_to_list(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1]) > 0]

    num_qubits = count_qubits(ham_opf)

    pos_dict_fix = {}

    for site_idx in range(n_site):
        for spin in range(2):
            ind = site_idx * 2 * (N_B_per_orbital + 1) + spin * (N_B_per_orbital + 1)
            pos_dict_fix[ind] = (0, site_idx, spin)

            for bath_ind in range(N_B_per_orbital):
                ind = (
                    site_idx * 2 * (N_B_per_orbital + 1)
                    + spin * (N_B_per_orbital + 1)
                    + (bath_ind + 1)
                )
                pos_dict_fix[ind] = (bath_ind + 1, site_idx, spin)

    result = {"num_qubit": num_qubits, "pos": pos_dict_fix, "pauli": ham}
    return result


def _chain_site_single_band_hamiltonian(
    n_site,
    N_B_per_orbital,
    U=1,
    V=1,
    t=1,
    e_list=None,
    encoding="jordan-wigner",
    verbose=0,
):
    """
    N_B_per_orbital: number of bath sites
    U : repulsion in impurity electron
    """
    # n_site = 2
    n_orbital = 2 * n_site
    N_B = N_B_per_orbital * n_orbital
    if e_list is None:
        e_list = [0.5 for i in range(N_B)]

    ham_f = FermionOperator()

    # impurity-impurity interaction
    if verbose:
        print("\n impurity-impurity interaction")
    for n in range(n_site):
        imp_up = 2 * n * (N_B_per_orbital + 1)
        imp_dn = (2 * n + 1) * (N_B_per_orbital + 1)
        ham_f += U * FermionOperator(f"{imp_up}^ {imp_up} {imp_dn}^ {imp_dn}")

        if verbose:
            print(f"{imp_up=}, {imp_dn=}")

    # impurity site hopping
    if verbose:
        print("\n impurity-impurity hopping")
    for n in range(n_site - 1):
        for sigma in [0, 1]:
            imp1 = 2 * (N_B_per_orbital + 1) * n + sigma
            imp2 = 2 * (N_B_per_orbital + 1) * ((n + 1) % n_site) + sigma
            if verbose:
                print(f"{imp1=}, {imp2=}")

            ham_f += V * (
                FermionOperator(f"{imp1}^ {imp2}") + FermionOperator(f"{imp2}^ {imp1}")
            )

    # impurity-bath hopping
    if verbose:
        print("\n impurity-bath hopping")

    for n in range(n_site):
        for sigma in [0, 1]:
            imp_index = (2 * n + sigma) * (N_B_per_orbital + 1)
            for i in range(N_B_per_orbital):
                bath_index = imp_index + i + 1

                if verbose:
                    print(f"{imp_index=}, {bath_index=}")
                ham_f += t * (
                    FermionOperator(f"{imp_index}^ {bath_index}")
                    + FermionOperator(f"{bath_index}^ {imp_index}")
                )

    # conduction
    count = 0
    if verbose:
        print("\n bath hopping")

    for n in range(n_site):
        for sigma in [0, 1]:
            for m in range(N_B_per_orbital):
                bath_index = 1 + m + (N_B_per_orbital + 1) * (2 * n + sigma)
                ham_f += e_list[count] * FermionOperator(f"{bath_index}^ {bath_index}")

                if verbose:
                    print(f"{count=}, {bath_index=}")

                count += 1

    if encoding == "jordan-wigner":
        encoder = jordan_wigner
    elif encoding == "bravyi-kitaev":
        encoder = bravyi_kitaev
    elif encoding == "fermion":
        encoder = lambda x: x

    return encoder(ham_f)


def square_site_single_band(
    L: int,
    N_B_per_orbital: int,
    U: float = 1,
    t: float = 1,
    e_list=None,
    encoding: str = "jordan-wigner",
):
    ham_opf = _square_site_single_band_hamiltonian(
        L, N_B_per_orbital, U=U, t=t, e_list=e_list, encoding=encoding
    )
    ham = _from_openfermion_to_list(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1]) > 0]

    num_qubits = count_qubits(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1]) > 0]

    # pos_dict_fix = {i:i for i in range(num_qubits)}
    n_site = L**2
    pos_dict_fix = {}
    for site_idx in range(n_site):
        for spin in range(2):
            ind = site_idx * 2 * (N_B_per_orbital + 1) + spin * (N_B_per_orbital + 1)
            pos_dict_fix[ind] = (0, site_idx, spin)

            for bath_ind in range(N_B_per_orbital):
                ind = (
                    site_idx * 2 * (N_B_per_orbital + 1)
                    + spin * (N_B_per_orbital + 1)
                    + (bath_ind + 1)
                )
                pos_dict_fix[ind] = (bath_ind + 1, site_idx, spin)

    result = {"num_qubit": num_qubits, "pos": pos_dict_fix, "pauli": ham}
    return result


def _square_site_single_band_hamiltonian(
    L, N_B_per_orbital, U=1, V=1, t=1, e_list=None, encoding="jordan-wigner", verbose=0
):
    """
    N_B_per_orbital: number of bath sites
    U : repulsion in impurity electron
    """
    n_site = L**2
    n_orbital = 2 * n_site
    N_B = N_B_per_orbital * n_orbital
    if e_list is None:
        e_list = [0.5 for i in range(N_B)]

    ham_f = FermionOperator()

    # impurity-impurity interaction
    if verbose:
        print("\n impurity-impurity interaction")
    for nx in range(L):
        for ny in range(L):
            n = nx + ny * L
            imp_up = 2 * n * (N_B_per_orbital + 1)
            imp_dn = (2 * n + 1) * (N_B_per_orbital + 1)
            ham_f += U * FermionOperator(f"{imp_up}^ {imp_up} {imp_dn}^ {imp_dn}")

            if verbose:
                print(f"{imp_up=}, {imp_dn=}")

    # impurity site hopping
    if verbose:
        print("\n impurity-impurity hopping")

    for nx in range(L):
        for ny in range(L):
            n = nx + ny * L
            for sigma in [0, 1]:
                n_ex = (nx + 1) % L + ny * L
                n_ey = nx + ((ny + 1) % L) * L

                imp = 2 * (N_B_per_orbital + 1) * n + sigma

                imp_ex = 2 * (N_B_per_orbital + 1) * n_ex + sigma
                imp_ey = 2 * (N_B_per_orbital + 1) * n_ey + sigma
                if verbose:
                    print(f"{imp=}, {imp_ex=}, {imp_ey=}")

                ham_f += V * (
                    FermionOperator(f"{imp}^ {imp_ex}")
                    + FermionOperator(f"{imp_ex}^ {imp}")
                )
                ham_f += V * (
                    FermionOperator(f"{imp}^ {imp_ey}")
                    + FermionOperator(f"{imp_ey}^ {imp}")
                )

    # impurity-bath hopping
    if verbose:
        print("\n impurity-bath hopping")
    for n in range(n_site):
        for sigma in [0, 1]:
            imp_index = (2 * n + sigma) * (N_B_per_orbital + 1)
            for i in range(N_B_per_orbital):
                bath_index = imp_index + i + 1

                if verbose:
                    print(f"{imp_index=}, {bath_index=}")
                ham_f += t * (
                    FermionOperator(f"{imp_index}^ {bath_index}")
                    + FermionOperator(f"{bath_index}^ {imp_index}")
                )

    # conduction
    count = 0
    if verbose:
        print("\n bath hopping")
    for n in range(n_site):
        for sigma in [0, 1]:
            for m in range(N_B_per_orbital):
                bath_index = 1 + m + (N_B_per_orbital + 1) * (2 * n + sigma)
                ham_f += e_list[count] * FermionOperator(f"{bath_index}^ {bath_index}")

                if verbose:
                    print(f"{count=}, {bath_index=}")

                count += 1

    if encoding == "jordan-wigner":
        encoder = jordan_wigner
    elif encoding == "bravyi-kitaev":
        encoder = bravyi_kitaev
    elif encoding == "fermion":
        encoder = lambda x: x

    return encoder(ham_f)
