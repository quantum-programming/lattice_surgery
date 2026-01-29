from __future__ import annotations
import numpy as np

_Pauli_I = np.eye(2, dtype=complex)
_Pauli_X = np.zeros(shape=(2, 2), dtype=complex)
_Pauli_X[1, 0] = _Pauli_X[0, 1] = 1
_Pauli_Z = np.eye(2, dtype=complex)
_Pauli_Z[1, 1] = -1
_Pauli_Y = 1.0j * _Pauli_X @ _Pauli_Z


def RX(theta: float) -> np.ndarray:
    return np.cos(theta / 2) * _Pauli_I - 1.0j * np.sin(theta / 2) * _Pauli_X


def RY(theta: float) -> np.ndarray:
    return np.cos(theta / 2) * _Pauli_I - 1.0j * np.sin(theta / 2) * _Pauli_Y


def RZ(theta: float) -> np.ndarray:
    return np.cos(theta / 2) * _Pauli_I - 1.0j * np.sin(theta / 2) * _Pauli_Z


def state_vector_to_density_matrix(vec: np.ndarray) -> np.ndarray:
    vec_2d = np.atleast_2d(vec)
    dm = vec_2d.T.conj() @ vec_2d
    return dm


def get_hadamard(rep: int = 1) -> np.ndarray:
    hadamard = np.array([[1, 1], [1, -1]])
    result = np.eye(1)
    for _ in range(rep):
        result = np.kron(result, hadamard)
    return result


def get_squared_norm(vec: np.ndarray) -> np.ndarray:
    return np.sum(np.abs(vec) ** 2)


def get_normalized_vector(vec: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    squared_norm = get_squared_norm(vec)
    if squared_norm < eps:
        raise ValueError("zero vector given")
    return vec / np.sqrt(squared_norm)
