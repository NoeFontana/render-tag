from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import generate_subject_records


@patch("render_tag.backend.projection.bridge")
@patch("render_tag.backend.projection._parse_board_config_and_layout")
@patch("render_tag.backend.projection._get_scene_transformations")
@patch("render_tag.backend.projection.is_facing_camera")
def test_generate_subject_records_skips_hidden(
    mock_facing, mock_transform, mock_layout_parse, mock_bridge
):
    """
    Test that generate_subject_records correctly handles visibility
    and board specs by delegating to generate_board_records.
    """
    mock_bridge.np = np
    mock_facing.return_value = True

    # 1. Setup Mock Object
    mock_obj = MagicMock()
    # Tag layout JSON
    board_spec_json = (
        '{"type": "charuco", "rows": 2, "cols": 2, "marker_size": 0.08, '
        '"square_size": 0.1, "dictionary": "tag36h11"}'
    )
    mock_obj.blender_obj = {"type": "BOARD", "board": board_spec_json, "keypoints_3d": []}

    # 2. Setup Mock Layout
    mock_sq = MagicMock()
    mock_sq.has_tag = True
    mock_sq.row = 0
    mock_sq.col = 0
    mock_sq.center = MagicMock(x=0.0, y=0.0)
    mock_sq.tag_id = 42

    mock_layout_obj = MagicMock()
    mock_layout_obj.squares = [mock_sq]

    from render_tag.generation.board import BoardSpec, BoardType

    spec = BoardSpec(
        rows=2, cols=2, square_size=0.1, marker_margin=0.01, board_type=BoardType.CHARUCO
    )

    mock_layout_parse.return_value = (mock_layout_obj, spec, ("charuco", 2, 2, 0.08, "tag36h11"))

    # 3. Setup Mock Transformations
    mock_transform.return_value = (
        np.eye(4),  # world_matrix
        np.eye(4),  # blender_cam_mat
        np.eye(3),  # k_matrix
        [640, 480],  # res
        (
            1.0,
            0.0,
            {"position": [0, 0, 1], "rotation_quaternion": [1, 0, 0, 0]},
            {"velocity": None, "shutter_time_ms": 0.0, "rolling_shutter_ms": 0.0, "fstop": None},
            np.array([0, 0, 10]),  # cam_location
            np.array([0, 0, 1]),  # world_normal
        ),  # meta
    )

    with patch("render_tag.backend.projection.project_points") as mock_proj:
        # Expected real projection result (TL, TR, BR, BL)
        mock_proj.return_value = np.array([[100, 100], [150, 100], [150, 150], [100, 150]])

        # ACT
        records = generate_subject_records(mock_obj, "test_img")

        # VERIFY
        # Should have at least 1 record (the TAG)
        assert len(records) >= 1
        tag_record = next(r for r in records if r.record_type == "TAG")

        # Check that it used the projected points
        assert tag_record.corners[0] == (100.0, 100.0)
        assert tag_record.corners[1] == (150.0, 100.0)
        assert tag_record.tag_id == 42
