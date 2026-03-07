from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from render_tag.backend.projection import generate_board_records


@patch("render_tag.backend.projection.bridge")
@patch("render_tag.backend.projection._parse_board_config_and_layout")
@patch("render_tag.backend.projection._get_scene_transformations")
def test_generate_board_records_skip_visibility_no_dummy(
    mock_transform, mock_layout, mock_bridge
):
    """
    Test that generate_board_records does NOT return dummy 20.0 offsets
    when skip_visibility=True. It should perform real projection.
    """
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 0]

    mock_obj = MagicMock()
    mock_obj.blender_obj = {"board": {"type": "charuco", "rows": 2, "cols": 2, "marker_size": 0.08, "square_size": 0.1, "dictionary": "tag36h11"}}
    
    # Mock Layout with one tag
    mock_sq = MagicMock()
    mock_sq.has_tag = True
    mock_sq.row = 0
    mock_sq.col = 0
    mock_sq.center = MagicMock(x=0.0, y=0.0)
    
    mock_layout_obj = MagicMock()
    mock_layout_obj.squares = [mock_sq]
    
    from render_tag.generation.board import BoardSpec, BoardType
    spec = BoardSpec(rows=2, cols=2, square_size=0.1, marker_margin=0.01, board_type=BoardType.CHARUCO)
    
    mock_layout.return_value = (mock_layout_obj, spec, ("charuco", 2, 2, 0.08, "tag36h11"))
    
    # Mock transformations
    mock_transform.return_value = (
        np.eye(4), # world_matrix
        np.eye(4), # blender_cam_mat
        np.eye(3), # k_matrix
        [640, 480], # res
        (1.0, 0.0, {"position": [0,0,1], "rotation_quaternion": [1,0,0,0]}) # meta
    )

    with patch("render_tag.backend.projection.project_points") as mock_proj:
        # Expected real projection result
        mock_proj.return_value = np.array([[100, 100], [150, 100], [150, 150], [100, 150]])
        
        # ACT: Call with skip_visibility=True
        records = generate_board_records(mock_obj, "test_img", skip_visibility=True)
        
        # 1 for the tag, 1 for the saddle point
        assert len(records) >= 1
        
        tag_record = next(r for r in records if r.record_type == "TAG")
        
        # Current (BUGGY) behavior would have corners starting at (0.0, 0.0) due to offset_x, offset_y = 0 * 20.0
        # and sizes of 10.0.
        # We want it to be [100, 100], etc. (real projection)
        assert tag_record.corners[0] == (100.0, 100.0), f"Expected real projection, got dummy {tag_record.corners[0]}"
        assert tag_record.corners[1] == (150.0, 100.0)

