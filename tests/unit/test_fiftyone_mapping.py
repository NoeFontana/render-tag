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
    """Test that corners are mapped to labeled keypoints correctly."""
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
    # Check points (relative to image size in FiftyOne, but let's assume raw for now
    # or handle normalization in implementation)
    points = [kp.points[0] for kp in keypoints.keypoints]
    assert points[0] == [100, 100]


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
        [-1.0, -1.0],  # sentinel
        [500.0, 600.0],
    ]

    result = map_calibration_keypoints(keypoints, width=1000.0, height=1000.0)

    # Only 3 visible keypoints
    assert len(result) == 3
    labels = [kp.label for kp in result]
    assert labels == ["0", "2", "4"]  # Preserves original indices
    # Verify normalization
    assert result[0].points == [[0.1, 0.2]]
    assert result[1].points == [[0.3, 0.4]]


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
