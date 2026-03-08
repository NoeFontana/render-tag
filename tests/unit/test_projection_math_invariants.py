from __future__ import annotations

import numpy as np
import pytest

from render_tag.generation.projection_math import (
    calculate_relative_pose,
    matrix_to_quaternion_wxyz,
)


def test_matrix_to_quaternion_invariants():
    """
    Verify that matrix_to_quaternion_wxyz enforces rotation matrix invariants.
    """
    # 1. Valid rotation matrix (Identity)
    identity = np.eye(3)
    quat = matrix_to_quaternion_wxyz(identity)
    assert quat == [1.0, 0.0, 0.0, 0.0]

    # 2. Uniform scale (should fail)
    scaled_matrix = np.eye(3) * 2.0
    with pytest.raises(AssertionError, match="Matrix is not orthogonal"):
        matrix_to_quaternion_wxyz(scaled_matrix)

    # 3. Non-uniform scale (should fail)
    non_uniform = np.diag([1.0, 2.0, 1.0])
    with pytest.raises(AssertionError, match="Matrix is not orthogonal"):
        matrix_to_quaternion_wxyz(non_uniform)

    # 4. Reflection (det = -1) (should fail)
    reflection = np.diag([-1.0, 1.0, 1.0])
    with pytest.raises(AssertionError, match=r"Matrix determinant is not \+1"):
        matrix_to_quaternion_wxyz(reflection)


def test_calculate_relative_pose_scale_invariance():
    """
    Verify that calculate_relative_pose extracts the same quaternion
    regardless of tag scale.
    """
    # Create a base rigid tag matrix
    tag_world = np.eye(4)
    # Give it some rotation
    angle = np.pi / 4
    c, s = np.cos(angle), np.sin(angle)
    # Rotate around X
    tag_world[:3, :3] = [[1, 0, 0], [0, c, -s], [0, s, c]]
    tag_world[:3, 3] = [1.0, 2.0, 3.0]

    # Camera at origin looking at +Z
    # (identity in Blender is -Z forward, but opencv conversion handles it)
    cam_world = np.eye(4)

    # Reference pose (unscaled)
    ref_pose = calculate_relative_pose(tag_world, cam_world)

    # Apply aggressive non-uniform scaling to the tag world matrix
    # (X * 0.1, Y * 5.0, Z * 2.0)
    scaled_tag_world = tag_world.copy()
    scaled_tag_world[:3, :3] = scaled_tag_world[:3, :3] @ np.diag([0.1, 5.0, 2.0])

    # Scaled pose
    scaled_pose = calculate_relative_pose(scaled_tag_world, cam_world)

    # Assertions
    np.testing.assert_allclose(
        ref_pose["rotation_quaternion"],
        scaled_pose["rotation_quaternion"],
        atol=1e-6,
        err_msg="Rotation quaternion changed after scaling tag world matrix!",
    )
    np.testing.assert_allclose(
        ref_pose["position"],
        scaled_pose["position"],
        atol=1e-6,
        err_msg="Position changed after scaling tag world matrix!",
    )
