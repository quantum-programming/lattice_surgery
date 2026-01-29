try:
    # this worked for openfermion v0.10.0, not for v1.1.0
    from openfermion.hamiltonians import MolecularData
except:
    # this worked for openfermion v1.1.0
    from openfermion import MolecularData


def assert_directory_exists(directory):
    import os

    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


from openfermionpyscf import run_pyscf
from openfermion import (
    normal_ordered,
    get_fermion_operator,
    jordan_wigner,
    bravyi_kitaev,
)


def H_chain_hamiltonian(
    r: float,
    n_H: int,
    occ_inds=[],
    multiplicity=1,
    charge=0,
    basis_type="sto-3g",
    encoding="jordan-wigner",
):
    """
    r : atomic distance of hydrogen chain
    n_H : number of hydrogen atoms
    occ_inds : index of frozen cores
    basis_type : basis type (sto-6g, 6-31g, ccpvdz, ccpvtz etc.)
    encoding : fermion, jordan-wigner, bravyi-kitaev
    """
    molecule = get_H_object(
        r, n_H, multiplicity=multiplicity, charge=charge, basis_type=basis_type
    )

    molecule = run_pyscf(
        molecule, run_mp2=True, run_cisd=True, run_ccsd=True, run_fci=False
    )

    act_inds = list(set(range(molecule.n_orbitals)) - set(occ_inds))
    molecular_ham = molecule.get_molecular_hamiltonian(occ_inds, act_inds)
    ham_f = normal_ordered(get_fermion_operator(molecular_ham))

    if encoding == "jordan-wigner":
        encode = jordan_wigner
    elif encoding == "bravyi-kitaev":
        encode = bravyi_kitaev
    elif encoding == "fermion":
        encode = lambda x: x
    return encode(ham_f)


def get_H_object(r, n_H, multiplicity=1, charge=0, basis_type="sto-3g"):
    geometry = [["H", [n * r, 0, 0]] for n in range(n_H)]
    molecule_type = "H%d" % n_H

    # filename = "molecules/" + molecule_type + "_" + basis_type + "/" + molecule_type + "_" + basis_type + "_" + "r_%.2f"%(r)
    directory = "./molecules/" + molecule_type + "_" + basis_type + "/"
    assert_directory_exists(directory)
    filename = directory + molecule_type + "_" + basis_type + "_" + "r_%.2f" % (r)

    molecule = MolecularData(
        geometry,
        basis_type,
        multiplicity,
        charge,
        filename=filename,
    )
    molecule.save()
    return molecule


def get_LiH_object(r, multiplicity=1, charge=0, basis_type="sto-3g"):
    geometry = [["Li", [0, 0, 0]], ["H", [r, 0, 0]]]
    molecule_type = "LiH"

    directory = "./molecules/" + molecule_type + "_" + basis_type + "/"
    assert_directory_exists(directory)
    filename = directory + molecule_type + "_" + basis_type + "_" + "r_%.2f" % (r)

    molecule = MolecularData(
        geometry,
        basis_type,
        multiplicity,
        charge,
        filename=filename,
    )
    molecule.save()
    return molecule


def get_H2O_object(r, degree=104.478, multiplicity=1, charge=0, basis_type="sto-3g"):
    rad = 2 * np.pi * (degree / 360)
    geometry = [
        ["O", [0, 0, 0]],
        ["H", [r, 0, 0]],
        ["H", [r * np.cos(rad), r * np.sin(rad), 0]],
    ]

    molecule_type = "H2O"

    directory = "./molecules/" + molecule_type + "_" + basis_type + "/"
    assert_directory_exists(directory)
    filename = directory + molecule_type + "_" + basis_type + "_" + "r_%.2f" % (r)

    molecule = MolecularData(
        geometry,
        basis_type,
        multiplicity,
        charge,
        filename=filename,
    )
    molecule.save()
    return molecule


def get_BeH2_object(r=1.3038, multiplicity=1, charge=0, basis_type="sto-3g"):
    geometry = [["Be", [0, 0, 0]], ["H", [r, 0, 0]], ["H", [-r, 0, 0]]]
    molecule_type = "BeH2"

    directory = "./molecules/" + molecule_type + "_" + basis_type + "/"
    assert_directory_exists(directory)
    filename = directory + molecule_type + "_" + basis_type + "_" + "r_%.2f" % (r)

    molecule = MolecularData(
        geometry,
        basis_type,
        multiplicity,
        charge,
        filename=filename,
    )
    molecule.save()
    return molecule


import numpy as np


def get_NH3_object(r=1.06995934, multiplicity=1, charge=0, basis_type="sto-3g"):
    # actual distance N-H is 1.06995934
    vN = np.array([0, 0, 0.149]) * (r / 1.07)
    vH1 = np.array([0, 0.947, -0.349]) * (r / 1.07)
    vH2 = np.array([0.820, -0.474, -0.349]) * (r / 1.07)
    vH3 = np.array([-0.820, -0.474, -0.349]) * (r / 1.07)
    geometry = [
        ["N", vN.tolist()],
        ["H", vH1.tolist()],
        ["H", vH2.tolist()],
        ["H", vH3.tolist()],
    ]

    molecule_type = "NH3"

    directory = "./molecules/" + molecule_type + "_" + basis_type + "/"
    assert_directory_exists(directory)
    filename = directory + molecule_type + "_" + basis_type + "_" + "r_%.2f" % (r)

    molecule = MolecularData(
        geometry, basis=basis_type, multiplicity=multiplicity, filename=filename
    )
    molecule.save()
    return molecule


def get_N2_object(r, multiplicity=1, charge=0, basis_type="sto-3g"):
    geometry = [["N", [0, 0, 0]], ["N", [r, 0, 0]]]
    molecule_type = "N2"

    directory = "./molecules/" + molecule_type + "_" + basis_type + "/"
    assert_directory_exists(directory)
    filename = directory + molecule_type + "_" + basis_type + "_" + "r_%.2f" % (r)

    molecule = MolecularData(
        geometry,
        basis_type,
        multiplicity,
        charge,
        filename=filename,
    )
    molecule.save()
    return molecule


def get_C2_object(r=1.2691, multiplicity=1, charge=0, basis_type="sto-3g"):
    geometry = [["C", [0, 0, 0]], ["C", [r, 0, 0]]]
    molecule_type = "C2"

    filename = (
        "./molecules/"
        + molecule_type
        + "_"
        + basis_type
        + "/"
        + molecule_type
        + "_"
        + basis_type
        + "_"
        + "r_%.2f" % (r)
    )
    molecule = MolecularData(
        geometry,
        basis_type,
        multiplicity,
        charge,
        filename=filename,
    )
    molecule.save()
    return molecule
