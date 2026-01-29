from openfermion import QubitOperator, count_qubits
import numpy as np

from .util import _from_openfermion_to_list

# def _schwinger_model_nogauss(N)


def schwinger_model(
    N,
    J: float = 1.0,
    q: float = 1.0,
    w: float = 1.0,
    m: float = 0,
    theta: float = 0.5,
):
    ham_opf = _schwinger_model_hamiltonian(N, J=J, q=q, w=w, m=m, theta=theta)
    ham = _from_openfermion_to_list(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1]) > 0]

    num_qubits = count_qubits(ham_opf)

    # raise Exception("This function is not implemented yet")
    pos_dict_fix = {}
    for ind in range(num_qubits):
        pos_dict_fix[ind] = (ind,)

    result = {"num_qubit": num_qubits, "pos": pos_dict_fix, "pauli": ham}
    return result


def _schwinger_model_hamiltonian(
    n_site: int,
    J: float = 1.0,
    q: float = 1.0,
    w: float = 1.0,
    m: float = 0,
    theta: float = 0.5,
):
    hamiltonian = QubitOperator()

    theta_list = [theta for i in range(n_site - 1)]

    # staggered term
    for n in range(n_site - 1):  # n runs from 0 to N-2
        staggered_z = 0
        for i in range(n + 1):  # i runs from 0 to n
            # coefficient =
            staggered_z += q * (QubitOperator(f"Z{i}") + (-1) ** i) / 2

        topological_term = QubitOperator("") * theta_list[n] / (2 * np.pi)

        hamiltonian += (staggered_z + topological_term) ** 2

    # spin-spin
    for n in range(n_site - 1):
        hamiltonian += QubitOperator(f"X{n} X{n+1}", w / 2)
        hamiltonian += QubitOperator(f"Y{n} Y{n+1}", w / 2)

    # magnetic field?
    for n in range(n_site):
        coefficient = m / 2 * ((-1) ** n)
        hamiltonian += QubitOperator(f"Z{n}", coefficient)

    return hamiltonian


def z2_lattice_gauge(L: int, h: float = 1.0, BCtype: str = "PBC"):
    ham_opf, pos_dict = _z2_lattice_gauge_hamiltonian_square(
        L, h=h, BCtype=BCtype, return_pos_dict=True
    )
    ham = _from_openfermion_to_list(ham_opf)

    # Reveom identity operator
    ham = [term for term in ham if len(term[1]) > 0]

    num_qubits = count_qubits(ham_opf)

    # raise Exception("This function is not implemented yet")
    pos_dict_fix = pos_dict
    # for ind in range(num_qubits):
    # pos_dict_fix[ind] = (ind, )

    result = {"num_qubit": num_qubits, "pos": pos_dict_fix, "pauli": ham}
    return result


def _z2_lattice_gauge_hamiltonian_square(
    L: int, h: float = 1.0, BCtype: str = "PBC", return_pos_dict=False, verbose=False
):
    assert BCtype == "PBC", "I am not sure if cylinder or OBC makes sense in this model"

    electronic_term = sum([1 - QubitOperator(f"X{i}") for i in range(2 * (L**2))])

    magnetic_term = 0

    pos_dict = {}

    for ix in range(L):
        for iy in range(L):
            p1 = ix + iy * (2 * L)
            p2 = ((ix + 1) % L + L) + iy * (2 * L)
            p3 = ix + ((iy + 1) % L) * (2 * L)
            p4 = (ix + L) + iy * (2 * L)

            if verbose:
                print(f"{p1=}, {p2=}, {p3=}, {p4=}")

            pos_dict[p1] = (ix, iy, 0)  # horizontal link
            pos_dict[p2] = ((ix + 1) % L, iy, 1)  # vertical link
            pos_dict[p3] = (ix, (iy + 1) % L, 0)  # horizontal link
            pos_dict[p4] = (ix, iy, 1)  # vertical link

            magnetic_term += h * QubitOperator(f"Z{p1} Z{p2} Z{p3} Z{p4}")

    if return_pos_dict:
        return electronic_term + magnetic_term, pos_dict
    else:
        return electronic_term + magnetic_term
