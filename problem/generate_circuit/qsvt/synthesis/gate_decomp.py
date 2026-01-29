from __future__ import annotations
import numpy as np
from .util import (
    RY,
    RZ,
    get_hadamard,
    get_squared_norm,
    state_vector_to_density_matrix,
    get_normalized_vector,
)


def state_decomp_1q(vec: np.ndarray) -> tuple[float, float, float]:
    """Decompose dim-2 vector to three angles

    Return tuple (theta_y, theta_z, theta_0) will regenerate given state vec as

    vec = exp(1.j * theta_0) @ RX(theta_x) @ RY(theta_y) @ np.array([1,0])

    Args:
        vec (np.ndarray): _description_

    Returns:
        tuple[float, float, float]: _description_
    """
    assert len(vec) == 2
    theta_y = np.arctan2(np.abs(vec[1]), np.abs(vec[0])) * 2
    if np.abs(vec[0]) < 1 / np.sqrt(2):
        rel = vec[0] / vec[1]
        theta_z = -np.angle(rel)
    else:
        rel = vec[1] / vec[0]
        theta_z = np.angle(rel)
    ref = RZ(theta_z) @ RY(theta_y) @ np.array([1, 0], dtype=complex)
    if np.abs(vec[0]) < 1 / np.sqrt(2):
        theta_0 = -np.angle(ref[1] / vec[1])
    else:
        theta_0 = -np.angle(ref[0] / vec[0])
    return (theta_y, theta_z, theta_0)


def state_decomp(vec: np.ndarray, eps: float = 1e-8) -> list:
    if not isinstance(vec, np.ndarray):
        vec = np.array(vec)
    assert vec.ndim == 1
    dim = vec.shape[0]
    assert dim & (dim - 1) == 0  # dim is 2^n
    assert np.allclose(get_squared_norm(vec), 1.0)

    num_qubit = int(np.log2(dim + 1e-10))
    assert num_qubit >= 1

    npsi = vec
    check_vec = vec
    result = {}
    for num_control in range(num_qubit - 1, -1, -1):
        psi = npsi
        npsi = np.zeros(shape=len(psi) // 2, dtype=complex)
        assert len(psi) == 2 ** (num_control + 1)
        check_matrix = np.eye(len(psi), dtype=complex)
        result[num_control] = {}
        for control_idx in range(0, 2**num_control, 1):
            small_psi = np.array([psi[control_idx * 2 + 0], psi[control_idx * 2 + 1]])
            amp = np.sqrt(get_squared_norm(small_psi))
            if amp < eps:
                theta_y, theta_z, theta_0 = (0.0, 0.0, 0.0)
            else:
                small_psi /= amp
                theta_y, theta_z, theta_0 = state_decomp_1q(small_psi)

            npsi[control_idx] = amp * np.exp(1.0j * theta_0)
            controls = tuple(np.arange(num_control))
            control_flips = tuple(map(int, format(control_idx, f"0{num_control}b")))
            item = {
                "name": "MPU2",
                "controls": controls,
                "control_flips": control_flips,
                "targets": [num_control],
                "theta_y": theta_y,
                "theta_z": theta_z,
            }
            result[num_control][control_flips] = item

            unitary = RZ(theta_z) @ RY(theta_y)
            check_matrix[
                2 * control_idx : 2 * control_idx + 2,
                2 * control_idx : 2 * control_idx + 2,
            ] = unitary

        check_matrix = np.kron(
            check_matrix, np.eye(2 ** (num_qubit - num_control - 1), dtype=complex)
        )
        check_vec = check_matrix.T.conj() @ check_vec

    ref_vec = np.zeros(len(vec), dtype=complex)
    ref_vec[0] = 1
    dm_ref_vec = state_vector_to_density_matrix(ref_vec)
    dm_check_vec = state_vector_to_density_matrix(check_vec)
    # print(dm_ref_vec)
    # print(dm_check_vec)
    assert np.allclose(dm_ref_vec, dm_check_vec)
    return result


def get_gray_code(n: int) -> list[int]:
    result = []
    for i in range(0, 2**n):
        gray = i ^ (i >> 1)
        result.append(gray)
    return result


def convert_gray(num_control: int, rotation_info: list) -> list:
    assert len(rotation_info) == 2**num_control
    if num_control == 0:
        result = []
        item = list(rotation_info.values())[0]
        result.append(
            {"name": "RY", "targets": [num_control], "angle": item["theta_y"]}
        )
        if not np.allclose(item["theta_z"], 0):
            result.append(
                {"name": "RZ", "targets": [num_control], "angle": item["theta_z"]}
            )
        return result
    control_list = get_gray_code(num_control)
    angles_y = [item["theta_y"] for item in rotation_info.values()]
    angles_z = [item["theta_z"] for item in rotation_info.values()]
    hadamard = get_hadamard(num_control)
    cvt_angles_y = np.mod(hadamard @ angles_y, np.pi * 2)
    cvt_angles_z = np.mod(hadamard @ angles_z, np.pi * 2)
    result = []
    gray_code_list = get_gray_code(num_control)
    gray_code_list = gray_code_list[1:] + [gray_code_list[0]]
    state = 0
    for angle_y, code in zip(cvt_angles_y, gray_code_list):
        result.append({"name": "RY", "targets": [num_control], "angle": angle_y})
        difs = state ^ code
        head = int(np.log2(difs + 1e-10))
        # print(format(state, f"0{num_control}b"), format(code, f"0{num_control}b"), format(difs, f"0{num_control}b"), head)
        result.append(
            {
                "name": "CX",
                "controls": [head],
                "control_flips": [
                    1,
                ],
                "targets": [num_control],
            }
        )
        state = code

    if not np.allclose(cvt_angles_z, np.zeros(shape=len(cvt_angles_z))):
        state = 0
        for angle_z, code in zip(cvt_angles_z, gray_code_list):
            result.append({"name": "RZ", "targets": [num_control], "angle": angle_z})
            difs = state ^ code
            head = int(np.log2(difs + 1e-10))
            # print(format(state, f"0{num_control}b"), format(code, f"0{num_control}b"), format(difs, f"0{num_control}b"), head)
            result.append(
                {
                    "name": "CX",
                    "controls": [head],
                    "control_flips": [
                        1,
                    ],
                    "targets": [num_control],
                }
            )
            state = code
    return result


def test_state_decomp_1q():
    for _ in range(1000):
        st = np.random.randn(2) + np.random.randn(2) * 1.0j
        st = get_normalized_vector(st)
        a, b, g = state_decomp_1q(st)
        vec = [1, 0]
        stt = np.exp(1.0j * g) * RZ(b) @ RY(a) @ vec
        assert np.allclose(st, stt)


def test_state_decomp():
    num_qubit = 3
    dim = 2**num_qubit
    st = np.random.randn(dim) + np.random.randn(dim) * 1.0j
    st = get_normalized_vector(st)
    raw_format = state_decomp(st)
    print(raw_format)


def test_state_decomp_gray():
    num_qubit = 4
    dim = 2**num_qubit
    st = np.random.randn(dim) + np.random.randn(dim) * 1.0j
    st = get_normalized_vector(st)
    raw_format = state_decomp(st)
    result = []
    for key, value in raw_format.items():
        res = convert_gray(key, value)
        result.extend(res)
    for gate in result:
        print(gate)
