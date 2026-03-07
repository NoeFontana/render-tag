from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import generate_subject_records


@patch("render_tag.backend.scene.bridge")
@patch("render_tag.backend.scene.compute_geometric_metadata")
@patch("render_tag.backend.scene.compute_charuco_layout")
def test_generate_subject_records_skips_hidden(mock_layout, mock_geo, mock_bridge):
    """
    Test that generate_subject_records correctly handles visibility
    and board specs.
    """
    mock_bridge.np = np

    # 1. Setup Mock Object
    mock_obj = MagicMock()
    # Tag layout JSON
    board_spec_json = (
        '{"rows": 2, "cols": 2, "marker_size": 0.08, "square_size": 0.1, "dictionary": "tag36h11"}'
    )
    mock_obj.blender_obj = {"type": "SUBJECT", "tag_layout": board_spec_json}

    # 2. Setup Mock Layout
    mock_layout_obj = MagicMock()
    from render_tag.generation.board import BoardSpec, BoardType

    spec = BoardSpec(
        rows=2, cols=2, square_size=0.1, marker_margin=0.01, board_type=BoardType.CHARUCO
    )

    mock_layout.return_value = (mock_layout_obj, spec, ("charuco", 2, 2, 0.08, "tag36h11"))

    # 3. Setup Mock Geometric Metadata
    # One visible TAG, one invisible TAG
    tag_visible = MagicMock()
    tag_visible.record_type = "TAG"
    tag_visible.is_visible = True
    tag_visible.corners = [(100.0, 100.0), (150.0, 100.0), (150.0, 150.0), (100.0, 150.0)]

    tag_hidden = MagicMock()
    tag_hidden.record_type = "TAG"
    tag_hidden.is_visible = False

    mock_geo.side_effect = [tag_visible, tag_hidden]

    # 4. Setup Mock Bridge bproc visibility check
    # We mock bproc.filter.visible_objects to return ONLY our visible tag
    mock_bridge.bproc.filter.visible_objects.return_value = [tag_visible]

    # ACT
    records = generate_subject_records(mock_obj, "test_img")

    # VERIFY
    # Should have 2 records (1 SUBJECT + 1 visible TAG)
    assert len(records) == 2
    assert any(r.record_type == "SUBJECT" for r in records)

    # Check that visible TAG is there and has real data
    tag_record = next(r for r in records if r.record_type == "TAG")

    # Current (BUGGY) behavior would have corners starting at (0.0, 0.0)
    # due to offset_x, offset_y = 0 * 20.0 and sizes of 10.0.
    # We want it to be [100, 100], etc. (real projection)
    assert tag_record.corners[0] == (100.0, 100.0), (
        f"Expected real projection, got dummy {tag_record.corners[0]}"
    )
    assert tag_record.corners[1] == (150.0, 100.0)
