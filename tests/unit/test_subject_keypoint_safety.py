import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from render_tag.backend.projection import generate_subject_records

@patch("render_tag.backend.projection.bridge")
@patch("render_tag.backend.projection.project_points")
@patch("render_tag.backend.projection.calculate_relative_pose")
def test_generate_subject_records_sparse_keypoints(mock_pose, mock_proj, mock_bridge):
    """
    Test that generate_subject_records handles subjects with < 4 keypoints 
    without crashing or failing pydantic validation.
    """
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = np.array([0, 0, 5])
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)
    
    mock_pose.return_value = {"position": [0,0,0], "rotation_quaternion": [1,0,0,0]}
    
    mock_obj = MagicMock()
    # Only ONE keypoint (e.g. center of a sphere)
    kps = [[0.0, 0.0, 0.0]]
    mock_obj.blender_obj = {
        "type": "SUBJECT",
        "tag_id": 1,
        "tag_family": "sphere",
        "keypoints_3d": kps,
    }
    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = np.array([0, 0, 0])
    
    # Mock projection to return ONE point
    mock_proj.return_value = np.array([[320.0, 240.0]])
    
    # ACT: Should not raise ValidationError or IndexError
    records = generate_subject_records(mock_obj, "test_img")
    
    # VERIFY
    assert len(records) == 1
    record = records[0]
    
    # If < 4, they might all be in 'corners' or 'keypoints' depending on implementation.
    # The requirement says handle safely. 
    # Current BUGGY implementation does corners=corners_2d[:4], 
    # which for len=1 gives a list of 1 tuple.
    # But writers might expect 4.
    assert len(record.corners) == 1
    assert record.keypoints is None
