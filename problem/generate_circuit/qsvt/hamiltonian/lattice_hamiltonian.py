from openfermion import QubitOperator
from openfermion.ops import QubitOperator, FermionOperator
import networkx as nx
from openfermion.ops import FermionOperator
from openfermion.ops import QubitOperator
from openfermion import get_sparse_operator
import numpy as np
import qutip as qt
import scipy

# convert operator


def openfermion_to_qutip(operator):
    mat = get_sparse_operator(operator).toarray()
    n_qubit = int(np.log2(mat.shape[0]))
    ret = qt.Qobj(mat, dims=[[2] * n_qubit, [2] * n_qubit])
    return ret


######################################
# basic operators
######################################


def pauli(a, i):
    if a == 0:
        return QubitOperator("X0 X0")
    elif a in [1, 2, 3]:
        return QubitOperator("%s%d" % (["X", "Y", "Z"][a - 1], i))
    else:
        raise Exception("choose a from 0, 1, 2, 3")


def random_pauli(n_qubit):
    op = QubitOperator("X0 X0")
    for i in range(n_qubit):
        op = op * pauli(np.random.randint(0, 4), i)
    return op


def pauli_op(a, i):
    """Pauli operator.
    attrib:
        a:int, 0 -> iden, 1 -> X, 2-> Y, 3 ->Z
        i:int, site index
    """
    if a == 0:
        return QubitOperator("")
    elif a in [1, 2, 3]:
        return QubitOperator("%s%d" % (["I", "X", "Y", "Z"][a], i))


def spin_operator(a, i, s=0.5):
    """Pauli-based expression of spin operator with general spin number s.
    The spin-1/2 mapping is based on arXiv:9911047, while we further need the projection operator so that Hilbert space is restricted to the one given by Spin number s,
    instead of the extended one.
    """
    assert a in [1, 2, 3]
    assert (2 * s) % 1 == 0, f"s={s} must be a half integer."
    if s == 0.5:
        return pauli_op(a, i)
    else:
        return sum([pauli_op(a, int(2 * s) * i + mu) for mu in range(int(2 * s))]) / 2


def proj_spin_s(i, s):
    assert (2 * s) % 1 == 0, f"s={s} must be a half integer."
    sx = spin_operator(1, 0, s=s)
    sy = spin_operator(2, 0, s=s)
    sz = spin_operator(3, 0, s=s)

    S2 = sx * sx + sy * sy + sz * sz
    ret = QubitOperator("")
    for _S in np.arange(s % 1, s, 1):
        ret = (
            ret
            * (S2 - QubitOperator("", coefficient=float(_S * (_S + 1))))
            * (1 / (s * (s + 1) - _S * (_S + 1)))
        )

    return ret


def _heisen(
    i: int,
    j: int,
    gauge=False,
    s=1 / 2,
    is_spin_operator_pauli=True,
):
    """Heisenberg interaction with general S spin.

    Attributes:
        i,j : site index
        gauge : Bool, whether to flip the sign of XX, YY interaction
        s  : quantum spin number
        is_spin_operator_pauli: Bool valid only for s=1/2. Whether the operator is spin operator of Pauli operator,
                                                which differs in factor 4.
    """

    assert 2 * s % 1 == 0, "s must be a half integer"
    if not is_spin_operator_pauli and s != 0.5:
        Warning("attribute is_spin_operator = True is neglected.")

    if s == 0.5:
        if gauge:
            op = (
                -QubitOperator("X%d X%d" % (i, j))
                - QubitOperator("Y%d Y%d" % (i, j))
                + QubitOperator("Z%d Z%d" % (i, j))
            )
        op = (
            QubitOperator("X%d X%d" % (i, j))
            + QubitOperator("Y%d Y%d" % (i, j))
            + QubitOperator("Z%d Z%d" % (i, j))
        )
        if not is_spin_operator_pauli:
            op = op / 4
    else:
        if gauge:
            op = (
                -spin_operator(1, i, s) * spin_operator(1, j, s)
                - spin_operator(2, i, s) * spin_operator(2, j, s)
                + spin_operator(3, i, s) * spin_operator(3, j, s)
            )
        else:
            op = (
                spin_operator(1, i, s) * spin_operator(1, j, s)
                + spin_operator(2, i, s) * spin_operator(2, j, s)
                + spin_operator(3, i, s) * spin_operator(3, j, s)
            )

    return op


def _szsz(i, j, is_spin_operator_pauli=True):
    return _sz(i, is_spin_operator_pauli) * _sz(j, is_spin_operator_pauli)


def _sxsx(i, j, is_spin_operator_pauli=True):
    return _sx(i, is_spin_operator_pauli) * _sx(j, is_spin_operator_pauli)


def _sysy(i, j, is_spin_operator_pauli=True):
    return _sy(i, is_spin_operator_pauli) * _sy(j, is_spin_operator_pauli)


def _sy(i, is_spin_operator_pauli=True):
    op = QubitOperator("Y%d" % (i))

    if not is_spin_operator_pauli:
        op = op / 2

    return op


def _sx(i, is_spin_operator_pauli=True):
    op = QubitOperator("X%d" % (i))

    if not is_spin_operator_pauli:
        op = op / 2

    return op


def _sz(i, is_spin_operator_pauli=True):
    op = QubitOperator("Z%d" % (i))

    if not is_spin_operator_pauli:
        op = op / 2

    return op


def fermion_hopping(i, j):
    return FermionOperator("%d^ %d" % (i, j)) + FermionOperator("%d^ %d" % (j, i))


def fermion_number_operator(i):
    return FermionOperator("%d^ %d" % (i, i))


######################################
# Graph-based Hamiltonian
######################################


def FermionHubbard_on_graph(graph, t=1, U=0, mu=0):
    """Fermionic Hubbard model defined on a graph.
    This corresponds to Eq. (56) in Babbush et al., PRX 8, 041015 (2018).
    graph: nx.Graph object
    t : float, hopping amplitude between edges
    U : float, repulsive on-site interaction
    mu : float, chemical potential, set to be mu = U/2 (half filling) if not provided.
    """

    ham = FermionOperator()
    if mu is None:
        mu = U / 2

    J1_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "J1"
    ]
    n_qubit = graph.number_of_nodes()
    # J2_edges = [e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "J2"]

    for e in J1_edges:
        i_up = 2 * e[0]
        i_down = 2 * e[0] + 1

        j_up = 2 * e[1]
        j_down = 2 * e[1] + 1
        # ham += hop(e[0], e[1])

        ham += (-t) * fermion_hopping(i_up, j_up)
        ham += (-t) * fermion_hopping(i_down, j_down)

    for v in range(n_qubit):
        i_up = 2 * v
        i_down = 2 * v + 1

        ham += U * fermion_number_operator(i_up) * fermion_number_operator(i_down)
        ham += (-mu) * fermion_number_operator(i_up)
        ham += (-mu) * fermion_number_operator(i_down)

    return ham


def J1J2Heisenberg_on_graph(graph, J2=0, is_spin_operator_pauli=True, s=0.5):
    """J1J2 Heisenberg model on a graph.
    graph: nx.Graph object. Each edge must be  "J1" and "J2"
    hx: float, magnetic field strength
    is_spin_operator_pauli : Bool, definition based on spin-1/2 operator.
    """

    ham = QubitOperator()

    J1_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "J1"
    ]
    J2_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "J2"
    ]

    if J1_edges == [] and J2_edges == []:
        raise Exception("graph object has no information on J1 or J2.")

    for e in J1_edges:
        ham += _heisen(e[0], e[1], is_spin_operator_pauli=is_spin_operator_pauli, s=s)
    for e in J2_edges:
        ham += J2 * _heisen(
            e[0], e[1], is_spin_operator_pauli=is_spin_operator_pauli, s=s
        )

    return ham


def TFI_on_graph(graph, hx=0, is_spin_operator_pauli=True):
    """Transverse field Ising model on a graph.
    hx: float, magnetic field strength
    is_spin_operator_pauli : Bool, definition based on spin-1/2 operator.
    """

    ham = QubitOperator()

    J1_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "J1"
    ]
    J2_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "J2"
    ]

    for e in J1_edges:
        ham += _szsz(e[0], e[1], is_spin_operator_pauli=is_spin_operator_pauli)

    N = graph.number_of_nodes()
    for i in range(N):
        magfield_term = hx * QubitOperator("Z%d" % i)
        if not is_spin_operator_pauli:
            magfield_term = magfield_term / 2
        ham += magfield_term

    return ham


######################################
# Underlying graphs
######################################


def square_lattice_graph(Nx, Ny, BCtype="PBC", with_J2_edges=False, verbose=0):
    """
    Nx: sites along x axis
    Ny: sites along y axis
    BCtype: OBC (open boundary), PBC (periodic boundary), or cylinder.
    Note that the cylinder is periodic along x-axis, but open along y-axis.

    """
    assert BCtype in ["OBC", "PBC", "cylinder"]

    g = nx.Graph()
    n_v = Nx * Ny
    pos_dict = {}

    for ix in range(Nx):
        for iy in range(Ny):
            i = ix + iy * Nx
            pos_dict[i] = (ix, iy)
            i_ex = (ix + 1) % Nx + iy * Nx
            i_ey = ix + ((iy + 1) % Ny) * Nx
            i_exy1 = (ix + 1) % Nx + ((iy + 1) % Ny) * Nx
            i_exy2 = (ix - 1) % Nx + ((iy + 1) % Ny) * Nx

            if verbose:
                print("\n(ix,iy) = ", (ix, iy))

            if not (BCtype == "OBC" and ix == Nx - 1):
                g.add_edge(i, i_ex, label="J1")
                if verbose:
                    print("(i, i_ex) = ", (i, i_ex))
            if not (BCtype in ["OBC", "cylinder"] and iy == Ny - 1):
                g.add_edge(i, i_ey, label="J1")
                if verbose:
                    print("(i, i_ey) = ", (i, i_ey))

            if with_J2_edges:

                # interaction between upperright
                if BCtype == "OBC" and (ix == Nx - 1 or iy == Ny - 1):
                    pass
                elif BCtype == "cylinder" and iy == Ny - 1:
                    pass
                else:
                    g.add_edge(i, i_exy1, label="J2")
                    if verbose:
                        print("(i, i_exy1) = ", (i, i_exy1))

                # interaction between upperleft
                if BCtype == "OBC" and (ix == 0 or iy == Ny - 1):
                    pass
                elif BCtype == "cylinder" and iy == Ny - 1:
                    pass
                else:
                    g.add_edge(i, i_exy2, label="J2")
                    if verbose:
                        print("(i, i_exy2) = ", (i, i_exy2))

    return g, pos_dict


def _old_square_lattice_graph(Nx, Ny, BCtype="PBC", with_J2_edges=False):
    """
    Nx: sites along x axis
    Ny: sites along y axis
    """

    g = nx.Graph()
    n_v = Nx * Ny
    pos_dict = {}
    # n_v = (4*n_hex_x + 2) *(n_hex_y + 1) + 2*(n_hex_y - 1)

    # nearest neighbor edges
    # for i in range(n_v-1):
    for ix in range(Nx):
        for iy in range(Ny):
            i = ix + iy * Nx
            pos_dict[i] = (ix, iy)
            i_ex = (ix + 1) % Nx + iy * Nx
            i_ey = ix + ((iy + 1) % Ny) * Nx
            i_exy1 = (ix + 1) % Nx + ((iy + 1) % Ny) * Nx
            i_exy2 = (ix - 1) % Nx + ((iy + 1) % Ny) * Nx

            if not (BCtype == "OBC" and ix == Nx - 1):
                g.add_edge(i, i_ex, label="J1")
            if not (BCtype == "OBC" and iy == Ny - 1):
                g.add_edge(i, i_ey, label="J1")

            if with_J2_edges:
                if not (BCtype == "OBC" and (ix == Nx - 1 or iy == Ny - 1)):
                    g.add_edge(i, i_exy1, label="J2")
                if not (BCtype == "OBC" and (ix == 0 or iy == Ny - 1)):
                    g.add_edge(i, i_exy2, label="J2")

    return g, pos_dict


def chain_graph(Nx, Ny=1, BCtype="PBC", with_J2_edges=False):
    """
    Nx: sites along x axis
    Ny: sites along y axis
    """

    assert Ny == 1
    g = nx.Graph()
    n_v = Nx
    # n_v = (4*n_hex_x + 2) *(n_hex_y + 1) + 2*(n_hex_y - 1)

    pos_dict = {}
    # nearest neighbor edges
    # for i in range(n_v-1):
    for ix in range(Nx):
        i = ix
        pos_dict[i] = (ix,)
        i_ex = (ix + 1) % Nx
        i_exx = (ix + 2) % Nx

        if not (BCtype == "OBC" and ix >= Nx - 1):
            g.add_edge(i, i_ex, label="J1")

        if with_J2_edges:
            if not (BCtype == "OBC" and ix >= Nx - 2):
                g.add_edge(i, i_exx, label="J2")

    return g, pos_dict


######################################
# Kitaev Hamiltonian
######################################


def KitaevHoneycombModel(
    Nx,
    Ny,
    Jxx=1,
    Jyy=1,
    Jzz=1,
    hz=0,
    hx=0,
    hy=0,
    is_spin_operator_pauli=True,
    verbose=0,
):
    ham = QubitOperator()

    graph = KitaevHoneycomb_graph(Nx, Ny, verbose=verbose)
    n_qubit = graph.number_of_nodes()
    Jxx_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "Jxx"
    ]
    Jyy_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "Jyy"
    ]
    Jzz_edges = [
        e for e in graph.edges if graph.get_edge_data(e[0], e[1])["label"] == "Jzz"
    ]

    for e in Jxx_edges:
        ham += Jxx * _sxsx(e[0], e[1], is_spin_operator_pauli=is_spin_operator_pauli)
    for e in Jyy_edges:
        ham += Jyy * _sysy(e[0], e[1], is_spin_operator_pauli=is_spin_operator_pauli)
    for e in Jzz_edges:
        ham += Jzz * _szsz(e[0], e[1], is_spin_operator_pauli=is_spin_operator_pauli)

    if hz != 0:
        for i in range(n_qubit):
            ham += hz * _sz(i, is_spin_operator_pauli)
    if hx != 0:
        for i in range(n_qubit):
            ham += hx * _sx(i, is_spin_operator_pauli)
    if hy != 0:
        for i in range(n_qubit):
            ham += hy * _sy(i, is_spin_operator_pauli)

    return ham


def KitaevHoneycomb_edges(
    Nx,
    Ny,
    verbose=0,
):

    Jxx_edges = []
    Jyy_edges = []
    Jzz_edges = []

    for iy in range(Ny):
        if verbose > 0:
            print(f"\n iy = {iy}")
        if iy == 0:
            for ix in range(Nx):
                i = 2 * ix
                i_ex = 2 * ix + 1
                if verbose > 0:
                    print(f"XX: ({i}, {i_ex})")
                Jxx_edges.append((i, i_ex))

                i = 2 * ix + 1
                i_ex = 2 * ix + 2
                if verbose > 0:
                    print(f"YY: ({i}, {i_ex})")
                Jyy_edges.append((i, i_ex))

            # vertical
            for jx in range(Nx + 1):
                i = 2 * jx
                i_ey = 2 * (2 * Nx + 1) - 2 * jx - 1

                if verbose > 0:
                    print(f"ZZ: ({i}, {i_ey})")
                Jzz_edges.append((i, i_ey))

        else:

            # horizontal
            for ix in range(Nx):
                i = 2 * ix + (2 * Nx + 2) * (iy - 1) + (2 * Nx + 1)
                i_ex = i + 1
                i_exx = i + 2

                if iy % 2 == 0:
                    if verbose > 0:
                        print(f"YY: ({i}, {i_ex})")
                        print(f"XX: ({i_ex}, {i_exx})")
                    Jxx_edges.append((i_ex, i_exx))
                    Jyy_edges.append((i, i_ex))
                else:
                    if verbose > 0:
                        print(f"XX: ({i}, {i_ex})")
                        print(f"YY: ({i_ex}, {i_exx})")
                    Jxx_edges.append((i, i_ex))
                    Jyy_edges.append((i_ex, i_exx))

            # last horizontal
            i = 2 * Nx - 1 + (2 * Nx + 2) * (iy - 1) + (2 * Nx + 1) + 1
            i_ex = i + 1
            if iy % 2 == 0:
                if verbose > 0:
                    print(f"YY: ({i}, {i_ex})")
                Jyy_edges.append((i, i_ex))
            else:
                if verbose > 0:
                    print(f"XX: ({i}, {i_ex})")
                Jxx_edges.append((i, i_ex))

            # vertical
            for ix in range(Nx + 1):
                i = 2 * ix + (2 * Nx + 2) * (iy - 1) + (2 * Nx + 1) + 1
                i_ey = i + 2 * (Nx - ix) * 2 + 1

                if verbose > 0:
                    print(f"ZZ: ({i}, {i_ey})")
                Jzz_edges.append((i, i_ey))

    # horizontal
    if verbose > 0:
        print(f"\n final horizontal line:")
    for ix in range(Nx):
        i = 2 * ix + (2 * Nx + 2) * (Ny - 1) + (2 * Nx + 1)
        i_ex = i + 1
        i_exx = i + 2

        if Ny % 2 == 0:
            if verbose > 0:
                print(f"YY: ({i}, {i_ex})")
                print(f"XX: ({i_ex}, {i_exx})")
            Jxx_edges.append((i_ex, i_exx))
            Jyy_edges.append((i, i_ex))
        else:
            if verbose > 0:
                print(f"XX: ({i}, {i_ex})")
                print(f"YY: ({i_ex}, {i_exx})")
            Jxx_edges.append((i, i_ex))
            Jyy_edges.append((i_ex, i_exx))

    return Jxx_edges, Jyy_edges, Jzz_edges


def KitaevHoneycomb_graph(Nx, Ny, verbose=0):
    g = nx.Graph()
    Jxx_edges, Jyy_edges, Jzz_edges = KitaevHoneycomb_edges(Nx, Ny, verbose=verbose)

    for e in Jxx_edges:
        g.add_edge(e[0], e[1], label="Jxx")

    for e in Jyy_edges:
        g.add_edge(e[0], e[1], label="Jyy")

    for e in Jzz_edges:
        g.add_edge(e[0], e[1], label="Jzz")

    return g


######################################
# Fermion Hamiltonian
######################################
def FermionHubbard_1d(L, U, mu=None, BCtype="OBC", Lshift=0):
    t = 1
    if mu is None:
        mu = U / 2
    ham = FermionOperator()
    shift = 2 * Lshift
    for ii in range(L):
        i_up = 2 * ii + shift
        i_down = 2 * ii + 1 + shift
        i_ex_up = (2 * ii + 2) % (2 * L) + shift
        i_ex_down = (2 * ii + 3) % (2 * L) + shift

        ham += U * fermion_number_operator(i_up) * fermion_number_operator(i_down)
        ham += (-mu) * fermion_number_operator(i_up)
        ham += (-mu) * fermion_number_operator(i_down)
        if BCtype == "PBC" or (BCtype == "OBC" and ii < L - 1):
            ham += -t * fermion_hopping(i_up, i_ex_up)
            ham += -t * fermion_hopping(i_down, i_ex_down)
    return ham


def random_fermion_hopping_all2all(n_fermion, su2_symmetric=True, seed=None):
    # Todo: allow spin up-down hopping
    # Todo: take spin up(down) site index instead of fermion number
    ret = FermionOperator()
    np.random.seed(seed)
    for ii in range(n_fermion):
        i_up = 2 * ii
        i_down = 2 * ii + 1
        for jj in range(ii + 1, n_fermion):
            j_up = 2 * jj
            j_down = 2 * jj + 1
            if su2_symmetric:
                ret += np.random.normal() * (
                    fermion_hopping(i_up, j_up) + fermion_hopping(i_down, j_down)
                )
            else:
                ret += np.random.normal() * fermion_hopping(i_up, j_up)
                ret += np.random.normal() * fermion_hopping(i_down, j_down)
                ret += np.random.normal() * fermion_hopping(i_up, j_down)
                ret += np.random.normal() * fermion_hopping(i_up, j_down)

    return ret


######################################
# Spin Hamiltonian
######################################


def rainbow_hamiltonian(n_qubit, r=0.5, hx=0):
    ham = QubitOperator()

    assert n_qubit % 2 == 0
    for i in range(n_qubit - 1):
        order = np.abs(((n_qubit - 1) // 2 - i))
        if order == 0:
            ham += _heisen(i, i + 1)
            # ham += _XY(i, i+1)
        else:
            ham += (r ** (2 * order - 1)) * _heisen(i, i + 1)
            # ham += (r**(2*order-1)) * _XY(i, i+1)

    for i in range(n_qubit):
        ham += hx * QubitOperator("X%d" % i)
    return ham


def Heisenberg_all2all(
    N,
    Nshift=0,
):
    ret = QubitOperator()
    for ii in range(N):
        for jj in range(ii + 1, N):
            i = ii + Nshift
            j = jj + Nshift
            ret += _heisen(i, j)
    return ret


def Heisenberg_1d(Nx, Nshift=0, BCtype="OBC", gauge=False):
    ret = QubitOperator()
    for ix in range(Nx):
        i = ix + Nshift
        i_ex = (ix + 1) % Nx + Nshift

        if not (BCtype == "OBC" and ix == Nx - 1):
            ret += _heisen(i, i_ex, gauge)
    return ret


def Heisenberg_2d(Nx, Ny, Nshift=0, BCtype="OBC", gauge=False):
    ret = QubitOperator()
    for ix in range(Nx):
        for iy in range(Ny):
            i = ix + iy * Nx + Nshift
            i_ex = (ix + 1) % Nx + iy * Nx + Nshift
            i_ey = ix + ((iy + 1) % Ny) * Nx + Nshift

            if not (BCtype == "OBC" and ix == Nx - 1):
                ret += _heisen(i, i_ex, gauge=gauge)
            if not (BCtype == "OBC" and iy == Ny - 1):
                ret += _heisen(i, i_ey, gauge=gauge)
    return ret


def random_2body(N, Nshift=0, n_qubit=None, seed=None, sig_1body=1, ratio=1):
    ret = QubitOperator()
    if n_qubit is None:
        n_qubit = N + Nshift
    else:
        assert N + Nshift <= n_qubit

    np.random.seed(seed)
    for ii in range(N):
        i = ii + Nshift
        ret += np.random.normal() * pauli(1, i) * sig_1body
        ret += np.random.normal() * pauli(2, i) * sig_1body
        ret += np.random.normal() * pauli(3, i) * sig_1body

        for jj in range(ii + 1, N):
            j = jj + Nshift

            if np.random.rand() > ratio:
                continue

            ret += np.random.normal() * _heisen(i, j)
    return ret


def get_ground_state(hamiltonian, return_energy=False):
    if hamiltonian == QubitOperator():
        gs_en = 0
        gsvec = np.array([1, 0])
    else:
        ham_sp = get_sparse_operator(hamiltonian)
        n_qubit = int(np.log2(ham_sp.shape[0]))

        if n_qubit < 12:
            vals, vecs = np.linalg.eigh(ham_sp.toarray())
        else:
            vals, vecs = scipy.sparse.linalg.eigsh(ham_sp, which="SA", k=20)
        gsvec = vecs[:, np.argmin(vals)]
        gs_en = np.min(vals)

    if return_energy:
        return gsvec, gs_en
    else:
        return gsvec
