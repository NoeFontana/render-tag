"""
Advanced unit tests for geometry math, focusing on edge cases.
"""

import numpy as np
import pytest

from render_tag.geometry.math import rotation_matrix_from_vectors, look_at_rotation


def test_rotation_matrix_alignment_edge_cases():
    # Case 1: Already aligned
    v1 = np.array([1, 0, 0])
    v2 = np.array([1, 0, 0])
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R, np.eye(3))
    assert np.allclose(R @ v1, v2)

    # Case 2: Exact opposite (180 degrees) - X axis
    v1 = np.array([1, 0, 0])
    v2 = np.array([-1, 0, 0])
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    # Check it's an orthogonal matrix
    assert np.allclose(R.T @ R, np.eye(3))

    # Case 3: Exact opposite (180 degrees) - Y axis
    v1 = np.array([0, 1, 0])
    v2 = np.array([0, -1, 0])
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    assert np.allclose(R.T @ R, np.eye(3))

    # Case 4: Random vectors
    v1 = np.array([1, 2, 3], dtype=float)
    v1 /= np.linalg.norm(v1)
    v2 = np.array([-4, 5, 1], dtype=float)
    v2 /= np.linalg.norm(v2)
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    assert np.allclose(R.T @ R, np.eye(3))

    # Case 5: Near opposite (testing epsilon)
    v1 = np.array([1, 0, 0], dtype=float)
    v2 = np.array([-1, 1e-11, 0], dtype=float) # Just outside exact opposite branch
    v2 /= np.linalg.norm(v2)
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    assert np.allclose(R.T @ R, np.eye(3))


def test_look_at_rotation_degenerate():
    # Forward is [0, 0, 1], Up is [0, 0, 1] (Parallel)
    f = np.array([0, 0, 1])
    up = np.array([0, 0, 1])
    R = look_at_rotation(f, up)
    
    # Forward is Z axis in world
    # Camera -Z is world Z => cam_z = [0, 0, -1]
    assert np.allclose(R[:, 2], -f)
    # Resulting matrix should still be orthogonal
    assert np.allclose(R.T @ R, np.eye(3))
    
    # Forward is opposite to up
    f = np.array([0, 0, -1])
    up = np.array([0, 0, 1])
    R = look_at_rotation(f, up)
    assert np.allclose(R[:, 2], -f)
    assert np.allclose(R.T @ R, np.eye(3))


def test_look_at_rotation_axes():
    # Forward along X, Up along Z
    f = np.array([1, 0, 0])
    up = np.array([0, 0, 1])
    R = look_at_rotation(f, up)
    
    # cam_z = -f = [-1, 0, 0]
    # x_axis = up x cam_z = [0, 0, 1] x [-1, 0, 0] = [0, -1, 0]
    # y_axis = cam_z x x_axis = [-1, 0, 0] x [0, -1, 0] = [0, 0, 1]
    
    assert np.allclose(R[:, 0], [0, -1, 0]) # X
    assert np.allclose(R[:, 1], [0, 0, 1])  # Y
    assert np.allclose(R[:, 2], [-1, 0, 0]) # Z
