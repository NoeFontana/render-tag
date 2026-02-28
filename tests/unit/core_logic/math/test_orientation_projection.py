"""
Tests for orientation preservation in the projection engine.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock

from render_tag.backend.projection import generate_subject_records
from render_tag.core.schema import DetectionRecord

@pytest.fixture
def mock_bridge(monkeypatch):
    """Mock BlenderBridge and project_points."""
    mock = MagicMock()
    monkeypatch.setattr("render_tag.backend.projection.bridge", mock)
    
    # Mock project_points to return inputs as outputs (identity projection)
    # but flattened to 2D for simplicity
    def mock_project(pts, *args, **kwargs):
        return pts[:, :2]
    
    monkeypatch.setattr("render_tag.backend.projection.project_points", mock_project)
    
    # Mock other math calls
    monkeypatch.setattr("render_tag.backend.projection.calculate_distance", lambda *args: 1.0)
    monkeypatch.setattr("render_tag.backend.projection.get_world_normal", lambda *args: np.array([0,0,1]))
    monkeypatch.setattr("render_tag.backend.projection.calculate_angle_of_incidence", lambda *args: 0.0)
    monkeypatch.setattr("render_tag.backend.projection.calculate_relative_pose", 
                        lambda *args: {"position": [0,0,0], "rotation_quaternion": [1,0,0,0]})
    
    return mock

def test_generate_subject_records_preserves_order(mock_bridge):
    """Verify that logical 3D order is preserved in 2D output."""
    bridge = mock_bridge
    
    # Setup mock object with keypoints in specific logical order
    # TL, TR, BR, BL (Clockwise in Y-down)
    logical_kps = [
        [10.0, 10.0, 0.0],
        [20.0, 10.0, 0.0],
        [20.0, 20.0, 0.0],
        [10.0, 20.0, 0.0]
    ]
    
    mock_obj = MagicMock()
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {
        "keypoints_3d": logical_kps,
        "type": "TAG",
        "tag_id": 1,
        "tag_family": "tag36h11"
    }.get(key, default)
    
    # Mock world matrix (Identity)
    mock_obj.get_local2world_mat.return_value = np.eye(4)
    bridge.np = np
    
    # Execute
    records = generate_subject_records(mock_obj, image_id="test_img")
    
    assert len(records) == 1
    corners_2d = records[0].corners
    
    # Verify that corners_2d matches logical_kps order (mapped to 2D)
    for i in range(4):
        assert corners_2d[i][0] == logical_kps[i][0]
        assert corners_2d[i][1] == logical_kps[i][1]

def test_projection_engine_is_agnostic_to_visual_shuffling(mock_bridge, monkeypatch):
    """
    Verify that even if visual order is 'inverted', the logical 
    payload order is strictly maintained.
    """
    bridge = mock_bridge
    
    # Logical order: TL, TR, BR, BL
    logical_kps = [
        [10.0, 10.0, 0.0],
        [20.0, 10.0, 0.0],
        [20.0, 20.0, 0.0],
        [10.0, 20.0, 0.0]
    ]
    
    # Shuffled CW: TR, BR, BL, TL
    shuffled_coords = np.array([
        [20.0, 10.0],
        [20.0, 20.0],
        [10.0, 20.0],
        [10.0, 10.0]
    ])
    monkeypatch.setattr("render_tag.backend.projection.project_points", lambda *args: shuffled_coords)
    
    mock_obj = MagicMock()
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {
        "keypoints_3d": logical_kps,
        "type": "TAG",
        "tag_id": 1,
        "tag_family": "tag36h11"
    }.get(key, default)
    
    mock_obj.get_local2world_mat.return_value = np.eye(4)
    bridge.np = np
    
    # Execute
    records = generate_subject_records(mock_obj, image_id="test_img")
    
    corners_2d = records[0].corners
    
    # Logical Corner 0 (TL) MUST be shuffled_coords[0] (which is (20,10))
    # because it corresponds to the first 3D keypoint.
    assert corners_2d[0][0] == 20.0
    assert corners_2d[0][1] == 10.0
