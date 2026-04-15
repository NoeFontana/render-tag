import fiftyone as fo


def test_metadata_hydration_mapping():
    """Test that detection objects are hydrated with custom metadata correctly."""
    from render_tag.viz.fiftyone_tool import hydrate_detection

    # Mock detection and rich truth record
    detection = fo.Detection(label="tag36h11")
    record = {
        "distance": 5.0,
        "angle_of_incidence": 45.0,
        "ppm": 100.0,
        "position": [1.0, 2.0, 3.0],
        "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
        "corners": [[0, 0], [10, 0], [10, 10], [0, 10]],
    }

    # ACT
    hydrate_detection(detection, record)

    # VERIFY
    assert detection["distance"] == 5.0
    assert detection["angle_of_incidence"] == 45.0
    assert detection["ppm"] == 100.0
    assert detection["position"] == [1.0, 2.0, 3.0]
    assert detection["rotation_quaternion"] == [1.0, 0.0, 0.0, 0.0]


def test_keypoint_mapping():
    """Test that corners are mapped to labeled keypoints with visibility correctly."""
    from render_tag.viz.fiftyone_tool import map_corners_to_keypoints

    corners = [[100, 100], [200, 100], [200, 200], [100, 200]]

    # ACT
    keypoints = map_corners_to_keypoints(corners)

    # VERIFY
    assert isinstance(keypoints, fo.Keypoints)
    assert len(keypoints.keypoints) == 4
    # Check labels
    labels = [kp.label for kp in keypoints.keypoints]
    assert labels == ["0", "1", "2", "3"]
    # Check visibility (default 2 for non-sentinel)
    for kp in keypoints.keypoints:
        assert kp.visibility == 2
        assert "margin" not in kp.tags


def test_keypoint_mapping_with_margin():
    """Test that corners in the margin zone are tagged correctly."""
    from render_tag.viz.fiftyone_tool import map_corners_to_keypoints

    # W=1000, H=1000, margin=50
    corners = [
        [10, 500],  # Left margin (v=1)
        [500, 10],  # Top margin (v=1)
        [990, 500],  # Right margin (v=1)
        [500, 500],  # Interior (v=2)
        [-1, -1],  # Sentinel (v=0)
    ]

    # ACT
    keypoints = map_corners_to_keypoints(corners, width=1000, height=1000, margin_px=50)

    # VERIFY
    kps = keypoints.keypoints
    assert kps[0].visibility == 1
    assert "margin" in kps[0].tags
    assert kps[1].visibility == 1
    assert "margin" in kps[1].tags
    assert kps[2].visibility == 1
    assert "margin" in kps[2].tags
    assert kps[3].visibility == 2
    assert "margin" not in kps[3].tags
    assert kps[4].visibility == 0
    assert "sentinel" in kps[4].tags


def test_keypoint_mapping_explicit_visibility():
    """Test mapping corners with explicit visibility flags from rich truth."""
    from render_tag.viz.fiftyone_tool import map_corners_to_keypoints

    corners = [[100, 100], [200, 100]]
    vis_flags = [2, 1]

    # ACT
    keypoints = map_corners_to_keypoints(corners, visibility_flags=vis_flags)

    # VERIFY
    assert keypoints.keypoints[0].visibility == 2
    assert keypoints.keypoints[1].visibility == 1
    assert "margin" in keypoints.keypoints[1].tags


def test_hydration_includes_board_definition():
    """Test that board_definition fields are flattened into detection."""
    from render_tag.viz.fiftyone_tool import hydrate_detection

    detection = fo.Detection(label="board_charuco")
    record = {
        "record_type": "BOARD",
        "distance": 1.5,
        "board_definition": {
            "type": "charuco",
            "rows": 5,
            "cols": 7,
            "square_size_mm": 30.0,
            "marker_size_mm": 22.5,
            "dictionary": "DICT_4X4_50",
            "total_keypoints": 24,
        },
    }

    hydrate_detection(detection, record)

    assert detection["board_type"] == "charuco"
    assert detection["board_rows"] == 5
    assert detection["board_cols"] == 7
    assert detection["square_size_mm"] == 30.0
    assert detection["total_keypoints"] == 24


def test_calibration_keypoints_filter_sentinels():
    """Test that sentinel keypoints are excluded from calibration keypoints."""
    from render_tag.viz.fiftyone_tool import map_calibration_keypoints

    keypoints = [
        [100.0, 200.0],
        [-1.0, -1.0],  # sentinel
        [300.0, 400.0],
    ]

    result = map_calibration_keypoints(keypoints, width=1000.0, height=1000.0)

    # Only 2 visible keypoints
    assert len(result) == 2
    labels = [kp.label for kp in result]
    assert labels == ["0", "2"]  # Preserves original indices
    # Default visibility is 2
    for kp in result:
        assert kp.visibility == 2
        assert "margin" not in kp.tags


def test_calibration_keypoints_with_visibility_flags():
    """Test calibration mapping with explicit visibility flags (v=1 support)."""
    from render_tag.viz.fiftyone_tool import map_calibration_keypoints

    keypoints = [
        [100.0, 200.0],
        [300.0, 400.0],
    ]
    vis_flags = [2, 1]

    result = map_calibration_keypoints(
        keypoints, width=1000.0, height=1000.0, visibility_flags=vis_flags
    )

    assert result[0].visibility == 2
    assert result[1].visibility == 1
    assert "margin" in result[1].tags


def test_calibration_skeleton_grid():
    """Test grid skeleton construction for calibration points."""
    from render_tag.viz.fiftyone_tool import build_calibration_skeleton

    skeleton = build_calibration_skeleton(rows=4, cols=5)

    # Inner grid: (4-1)*(5-1) = 12 points
    assert len(skeleton.labels) == 12

    # Horizontal edges: 3 rows * 3 edges per row = 9
    # Vertical edges: 3 cols (well, 4 cols) * 2 vert edges each... let's count
    # row 0: (0,1),(1,2),(2,3) -> 3 horizontal
    # row 1: (4,5),(5,6),(6,7) -> 3 horizontal
    # row 2: (8,9),(9,10),(10,11) -> 3 horizontal
    # vertical: (0,4),(1,5),(2,6),(3,7),(4,8),(5,9),(6,10),(7,11) -> 8
    # Total: 9 + 8 = 17
    assert len(skeleton.edges) == 17
