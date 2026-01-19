"""
Unit tests for math_utils module.
"""

from __future__ import annotations

import numpy as np
import pytest
from render_tag.geometry.math import (
    compute_polygon_area,
    make_transformation_matrix,
    look_at_rotation,
)


def test_compute_polygon_area():
    # Unit square
    points = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    assert compute_polygon_area(points) == pytest.approx(1.0)

    # Triangle
    points = np.array([[0, 0], [2, 0], [0, 2]])
    assert compute_polygon_area(points) == pytest.approx(2.0)

    # Empty/Insufficient points
    assert compute_polygon_area(np.array([[0, 0]])) == 0.0


def test_make_transformation_matrix():
    translation = np.array([1, 2, 3])
    rotation = np.eye(3)
    mat = make_transformation_matrix(translation, rotation)

    assert mat.shape == (4, 4)
    assert np.allclose(mat[:3, :3], rotation)
    assert np.allclose(mat[:3, 3], translation)
    assert mat[3, 3] == 1.0


def test_look_at_rotation_forward():
    # Camera at (0, 0, 1) looking at (0, 0, 0)
    # Forward vector is (0, 0, -1)
    forward = np.array([0, 0, -1])
    R = look_at_rotation(forward)

    # Camera axes in world coordinates
    # cam_z = -f = (0, 0, 1)
    # world_up = (0, 0, 1) -> Degenerate case handled by look_at_rotation
    # It should still produce a valid rotation matrix (orthogonal)
    assert np.allclose(R.T @ R, np.eye(3))
    assert np.isclose(np.linalg.det(R), 1.0)


def test_look_at_rotation_alignment():
    # Pointing along X axis
    forward = np.array([1, 0, 0])
    R = look_at_rotation(forward)

    # cam_z = -f = (-1, 0, 0)
    # cam_x = up(0,0,1) x cam_z(-1,0,0) = (0, -1, 0)
    # cam_y = cam_z(-1,0,0) x cam_x(0,-1,0) = (0, 0, 1)

    expected_x = np.array([0, -1, 0])
    expected_y = np.array([0, 0, 1])
    expected_z = np.array([-1, 0, 0])

    assert np.allclose(R[:, 0], expected_x)
    assert np.allclose(R[:, 1], expected_y)
    assert np.allclose(R[:, 2], expected_z)
