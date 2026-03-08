from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import _get_scene_transformations


@patch("render_tag.backend.projection.bridge")
def test_reflected_board_matrix_preservation(mock_bridge):
    """
    Test that _get_scene_transformations preserves reflections
    (negative determinants) instead of forcing them positive.
    """
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = np.array([0, 0, 5])
    mock_bridge.bpy.context.scene.render.resolution_x = 640
    mock_bridge.bpy.context.scene.render.resolution_y = 480
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    mock_obj = MagicMock()
    # Reflected world matrix (Scale X by -1)
    world_matrix = np.eye(4)
    world_matrix[0, 0] = -1.0

    mock_obj.get_local2world_mat.return_value = world_matrix
    mock_obj.get_location.return_value = np.array([0, 0, 0])

    with (
        patch("render_tag.backend.projection.get_world_normal"),
        patch("render_tag.backend.projection.calculate_distance"),
        patch("render_tag.backend.projection.calculate_angle_of_incidence"),
        patch("render_tag.backend.projection.calculate_relative_pose"),
    ):
        res_matrix, _, _, _, meta = _get_scene_transformations(mock_obj)
        is_mirrored = meta[-1]

        # VERIFY: The matrix should be sanitized to SO(3) (det=1), and is_mirrored should be True
        det = np.linalg.det(res_matrix[:3, :3])
        assert np.isclose(det, 1.0), f"Determinant should be 1.0 after sanitization, got {det}"
        assert is_mirrored is True, "is_mirrored flag should be True for reflected object"
