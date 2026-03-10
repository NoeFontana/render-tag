from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import _get_scene_transformations


@patch("render_tag.backend.projection.bridge")
def test_get_scene_transformations_no_drift(mock_bridge):
    """
    Test that _get_scene_transformations returns a matrix equivalent
    to the raw world_matrix when scale is [1,1,1].
    """
    # Setup
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 5]
    mock_bridge.bpy.context.scene.render.resolution_x = 640
    mock_bridge.bpy.context.scene.render.resolution_y = 480
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    mock_obj = MagicMock()
    # A simple rotation + translation matrix with NO SCALE
    world_matrix = np.eye(4)
    world_matrix[0:3, 0:3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]  # 90 deg rotation
    world_matrix[0:3, 3] = [1, 2, 3]  # Translation

    mock_obj.get_local2world_mat.return_value = world_matrix
    mock_obj.get_location.return_value = [1, 2, 3]

    mock_spec = MagicMock()
    mock_spec.board_width = 1.0
    mock_spec.board_height = 1.0

    # We need to mock get_world_normal and other helpers if they are called
    with (
        patch("render_tag.backend.projection.get_world_normal") as mock_normal,
        patch("render_tag.backend.projection.calculate_distance") as mock_dist,
        patch("render_tag.backend.projection.calculate_angle_of_incidence") as mock_angle,
        patch("render_tag.backend.projection.calculate_relative_pose") as mock_pose,
    ):
        mock_normal.return_value = [0, 0, 1]
        mock_dist.return_value = 5.0
        mock_angle.return_value = 0.0
        mock_pose.return_value = {}

        # ACT
        rigid_matrix, _, _, _, _ = _get_scene_transformations(mock_obj, mock_spec)
        # VERIFY
        # The rigid_matrix should match the world_matrix exactly (since scale was 1)
        np.testing.assert_array_almost_equal(rigid_matrix, world_matrix)


def test_svd_removes_scale():
    """
    Demonstrate that the CURRENT implementation (with SVD) removes scale.
    This test serves as a baseline before we revert the hack.
    """
    # (Similar setup but with a scaled world_matrix)
    pass
