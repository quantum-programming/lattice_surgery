from openfermion import jordan_wigner, bravyi_kitaev
from .lattice_hamiltonian import FermionHubbard_on_graph
from .lattice_hamiltonian import square_lattice_graph
from .util import _from_openfermion_to_list


def FermiHubbard2D(
    lattice: int,
    boundary_type: str,
    t: float = 1,
    U: float = 4,
    mu: float = 0,
    decompodition: str = "jordan",
) -> list:
    assert boundary_type in ["OBC", "PBC", "cylinder"]
    num_qubit = lattice**2 * 2
    graph, pos_dict = square_lattice_graph(Nx=lattice, Ny=lattice, BCtype=boundary_type)
    ham = FermionHubbard_on_graph(graph, t=t, U=U, mu=mu)
    if decompodition == "jordan":
        ham = jordan_wigner(ham)
    else:
        ham = bravyi_kitaev(ham)
    ham = _from_openfermion_to_list(ham)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1]) > 0]

    pos_dict_fix = {}
    for ind in range(len(pos_dict)):
        pos_dict_fix[ind * 2] = (*pos_dict[ind], 0)
        pos_dict_fix[ind * 2 + 1] = (*pos_dict[ind], 1)

    result = {"num_qubit": num_qubit, "pos": pos_dict_fix, "pauli": ham}
    return result
