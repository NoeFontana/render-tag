import numpy as np
import pytest
from unittest.mock import MagicMock, patch
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
    
    with patch("render_tag.backend.projection.get_world_normal"), \
         patch("render_tag.backend.projection.calculate_distance"), \
         patch("render_tag.backend.projection.calculate_angle_of_incidence"), \
         patch("render_tag.backend.projection.calculate_relative_pose"):
        
        res_matrix, _, _, _, _ = _get_scene_transformations(mock_obj)
        
        # VERIFY: The negative determinant should be preserved
        det = np.linalg.det(res_matrix[:3, :3])
        assert det < 0, f"Determinant should be negative for reflected object, got {det}"
        assert np.isclose(det, -1.0), f"Expected det -1.0, got {det}"
