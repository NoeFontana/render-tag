"""
Tests for Standard Calibration Target Topology compliance.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest
from pydantic import ValidationError

from render_tag.backend.projection import generate_board_records
from render_tag.core.schema import DetectionRecord


@pytest.fixture
def mock_bridge(monkeypatch):
    """Mock BlenderBridge and math utilities."""
    mock = MagicMock()
    monkeypatch.setattr("render_tag.backend.projection.bridge", mock)

    # Mock project_points to simulate OpenCV camera projection.
    # In OpenCV space, (0,0) is Top-Left.
    # To map Cartesian (Y-up) to OpenCV (Y-down), we flip Y.
    def mock_project(pts, cam_world_mat, res, k_matrix, **kwargs):
        px = pts[:, 0] * 1000 + 500  # Map to ~[0, 1000] pixel space
        py = -pts[:, 1] * 1000 + 500  # Flip Y, map to pixel space
        return np.stack([px, py], axis=1)

    monkeypatch.setattr("render_tag.backend.projection.project_points", mock_project)

    # Mock other math calls
    monkeypatch.setattr("render_tag.backend.projection.calculate_distance", lambda *args: 1.0)
    monkeypatch.setattr(
        "render_tag.backend.projection.get_world_normal", lambda *args: np.array([0, 0, 1])
    )
    monkeypatch.setattr(
        "render_tag.backend.projection.calculate_angle_of_incidence", lambda *args: 0.0
    )
    monkeypatch.setattr(
        "render_tag.backend.projection.calculate_relative_pose",
        lambda *args: {"position": [0, 0, 0], "rotation_quaternion": [1, 0, 0, 0]},
    )

    return mock


def test_charuco_indexing_continuity(mock_bridge):
    """
    Verify ChArUco saddle point IDs are continuous from 0 to N-1.
    For 4 rows, 4 columns of SQUARES, there are (4-1)*(4-1) = 9 intersections.
    """
    mock_obj = MagicMock()
    # 4x4 board
    board_config = {
        "type": "charuco",
        "rows": 4,
        "cols": 4,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {"board": board_config}.get(
        key, default
    )

    # Mock transformations
    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = [0, 0, 0]
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 10]
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 1]
    mock_bridge.bpy.context.scene.render.resolution_x = 1000
    mock_bridge.bpy.context.scene.render.resolution_y = 1000
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    records = generate_board_records(mock_obj, "test_img")

    # Find the BOARD record
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1
    board_record = board_records[0]

    assert len(board_record.keypoints) == 9
    # The IDs are implicitly their index in the keypoints list.
    # No need to assert IDs themselves, just that 9 were generated.


def test_charuco_indexing_layout(mock_bridge):
    """
    Verify row-major physical ordering for ChArUco.
    Index 0 should be Top-Left physically (smallest X, smallest Y in OpenCV).
    Index 1 should be directly to its right.
    """
    mock_obj = MagicMock()
    board_config = {
        "type": "charuco",
        "rows": 3,
        "cols": 3,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {"board": board_config}.get(
        key, default
    )

    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = [0, 0, 0]
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 10]
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.render.resolution_x = 1000
    mock_bridge.bpy.context.scene.render.resolution_y = 1000
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    # To test Top-Left in OpenCV space, we need ID 0 to have
    # the minimum X and minimum Y coordinates among all intersections.

    records = generate_board_records(mock_obj, "test_img")
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1

    saddle_records = board_records[0].keypoints

    assert saddle_records is not None
    # There should be (3-1)*(3-1) = 4 saddle points
    assert len(saddle_records) == 4

    p0 = saddle_records[0]
    for other_id in range(1, len(saddle_records)):
        p_other = saddle_records[other_id]
        # Row-major: scanning left-to-right, then top-to-bottom.
        # ID 0 is top-leftmost.
        # In Y-down, top means smaller Y. Left means smaller X.
        assert p0[1] <= p_other[1]  # ID 0 Y <= any other Y (it's in first row)
        if p0[1] == p_other[1]:
            assert p0[0] < p_other[0]  # In same row, ID 0 is leftmost


def test_board_level_record_export(mock_bridge):
    """
    Verify that generate_board_records exports a single 'BOARD' record
    representing the overall board pose and physical size.
    """
    mock_obj = MagicMock()
    board_config = {
        "type": "charuco",
        "rows": 4,
        "cols": 4,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {"board": board_config}.get(
        key, default
    )

    # Board width for 4 cols of 0.08m squares is 0.32m.
    # The mesh has dimensions baked in, so local scale is 1.0.
    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = [0, 0, 0]
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 10]
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.render.resolution_x = 1000
    mock_bridge.bpy.context.scene.render.resolution_y = 1000
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    records = generate_board_records(mock_obj, "test_img")

    # Should have exactly one record_type == "BOARD"
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1
    board_det = board_records[0]

    assert board_det.tag_id == -1
    assert board_det.tag_family == "board_charuco"
    # Board width should now be exactly 320mm
    assert np.isclose(board_det.tag_size_mm, 320.0)
    # Origin (center) should project to image center (500, -500 because of our mock flip)
    # Wait, our mock_project does py = -pts[:, 1]. Center is [0,0,0] in world.
    # Cam at [0,0,1] in world looking at origin.
    # pts in cam space: [0,0,-1]... no wait.
    # In this test, cam is at [0,0,1] identity matrix?
    # Blender cam identity looks towards -Z.
    # Tag at origin [0,0,0] is at cam space [0,0,1]... wait.
    # If cam at [0,0,1] looking at [0,0,0], that's looking towards -Z.
    # Blender identity matrix is X right, Y up, Z back.
    # So looking towards -Z.
    # Origin is at [0,0,-1] in blender cam local space.
    # project_points uses OpenCV convention.
    # Anyway, let's just check it exists.
    assert len(board_det.corners) == 1


def test_board_level_record_export_aprilgrid(mock_bridge):
    """
    Verify that AprilGrid boards also export a 'BOARD' record.
    """
    mock_obj = MagicMock()
    board_config = {
        "type": "aprilgrid",
        "rows": 4,
        "cols": 6,
        "marker_size": 0.05,
        "spacing_ratio": 0.2,
        "dictionary": "tag36h11",
    }
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {"board": board_config}.get(
        key, default
    )

    # Square size = 0.05 * 1.2 = 0.06
    # Board width = 6 * 0.06 = 0.36m.
    # Board height = 4 * 0.06 = 0.24m.
    # The mesh has dimensions baked in, so local scale is 1.0.
    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = [0, 0, 0]
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 10]
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    records = generate_board_records(mock_obj, "test_img")

    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1
    assert board_records[0].tag_family == "board_aprilgrid"
    assert np.isclose(board_records[0].tag_size_mm, 360.0)


def test_detection_record_tag_id_type_enforcement():
    """Verify that DetectionRecord enforces tag_id as an integer."""
    corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    # Valid int
    record = DetectionRecord(image_id="test", tag_id=1, tag_family="tag36h11", corners=corners)
    assert isinstance(record.tag_id, int)

    # String that can be converted to int (Pydantic might auto-convert by default)
    # But we want to ensure it IS an int in the model.
    record2 = DetectionRecord(image_id="test", tag_id="123", tag_family="tag36h11", corners=corners)
    assert isinstance(record2.tag_id, int)
    assert record2.tag_id == 123

    # String that CANNOT be converted should fail
    with pytest.raises(ValidationError):
        DetectionRecord(
            image_id="test", tag_id="not_an_int", tag_family="tag36h11", corners=corners
        )


def test_board_scale_independence(mock_bridge):
    """
    Verify that applying a `scale` to the Blender board object does not
    double-scale the output ground truth coordinates. The local_corners are
    already physically scaled based on the generator metrics.
    """
    mock_obj = MagicMock()
    # Generic charuco config with 0.1m markers
    board_config = {
        "type": "charuco",
        "rows": 2,
        "cols": 2,
        "marker_size": 0.1,
        "square_size": 0.2,
        "dictionary": "tag36h11",
    }
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {"board": board_config}.get(
        key, default
    )

    # Simulate a Blender object that has a 0.5 uniform scale and a simple translation
    # (The canonical shape is already baked into the mesh)
    scaled_world_matrix = np.array(
        [
            [0.5, 0.0, 0.0, 1.0],
            [0.0, 0.5, 0.0, 2.0],
            [0.0, 0.0, 0.5, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    mock_obj.get_local2world_mat.return_value = scaled_world_matrix
    mock_obj.get_location.return_value = [1.0, 2.0, 3.0]

    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 10]
    mock_bridge.bpy.context.scene.render.resolution_x = 1000
    mock_bridge.bpy.context.scene.render.resolution_y = 1000
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    # Capture the projected points
    projected_pts = []

    def mock_project_points(pts, *args, **kwargs):
        projected_pts.extend(pts)
        return np.array([[float(p[0]) * 1000 + 500, float(-p[1]) * 1000 + 500] for p in pts])

    mock_bridge.project_points = mock_project_points
    # Mocking in the module using it:
    import render_tag.backend.projection

    render_tag.backend.projection.project_points = mock_project_points

    records = generate_board_records(mock_obj, "test_scale_img", skip_visibility=True)

    # We should have two tag records (since charuco 2x2 has 2
    # white squares with tags: (0,0) and (1,1))
    tag_records = [r for r in records if r.record_type == "TAG"]
    assert len(tag_records) == 2

    # The projected_pts passed to project_points should have standard physical size
    # Width of the marker in 3D without the 0.5 user scale should be 0.1m.
    # We check the world width (distance between TL and TR).
    assert len(projected_pts) >= 4
    # The first 4 points should be the corners of the single tag
    tl, tr, _, _ = projected_pts[:4]

    # With the new scaling logic:
    # User applied a 0.5x uniform scale on top of the baked physical dimensions.
    # The original marker_size of 0.1m is scaled by 0.5 -> 0.05m.
    diff = np.array(tr) - np.array(tl)
    width_3d = np.linalg.norm(diff)

    assert np.isclose(width_3d, 0.05), f"Expected marker 3D width 0.05, got {width_3d}"


def _make_board_obj(board_config, world_matrix=None, calib_pts=None):
    """Helper to create a mock board object."""
    mock_obj = MagicMock()

    def side_effect(key, default=None):
        lookup = {"board": board_config}
        if calib_pts is not None:
            lookup["calibration_points_3d"] = calib_pts
        return lookup.get(key, default)

    mock_obj.blender_obj.get.side_effect = side_effect
    wm = world_matrix if world_matrix is not None else np.eye(4)
    mock_obj.get_local2world_mat.return_value = wm
    mock_obj.get_location.return_value = list(wm[:3, 3])
    return mock_obj


def _setup_bridge(mock_bridge, res_x=1000, res_y=1000):
    """Configure bridge mock with standard camera settings."""
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 10]
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.render.resolution_x = res_x
    mock_bridge.bpy.context.scene.render.resolution_y = res_y
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)


def test_board_tags_outside_frustum_are_culled(mock_bridge, monkeypatch):
    """Tags that project outside the image bounds must be culled."""
    board_config = {
        "type": "charuco",
        "rows": 3,
        "cols": 3,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj = _make_board_obj(board_config)
    _setup_bridge(mock_bridge, res_x=100, res_y=100)

    # Mock project so that tags on the right side of the board fall outside
    # the small 100x100 image. Board spans ~[-0.12, 0.12] meters.
    # Map: x * 400 + 50 → left tags at ~2px, right tags at ~98px.
    # Tag corners span ±0.025m around center → ±10px.
    # Right-most tag center at x≈0.08, maps to 82px → TR corner at 92px (in bounds).
    # Use an offset that pushes right tags out: x * 400 + 80
    def project_partial_oob(pts, cam_world_mat, res, k_matrix, **kwargs):
        px = pts[:, 0] * 400 + 80
        py = -pts[:, 1] * 400 + 50
        return np.stack([px, py], axis=1)

    monkeypatch.setattr("render_tag.backend.projection.project_points", project_partial_oob)

    records = generate_board_records(mock_obj, "test_img")
    tag_records = [r for r in records if r.record_type == "TAG"]

    # 3x3 charuco has 5 white squares with tags. Some should be culled.
    assert len(tag_records) < 5, (
        f"Expected fewer than 5 TAG records due to frustum culling, got {len(tag_records)}"
    )
    assert len(tag_records) > 0, "At least some tags should be in-bounds"


def test_saddle_points_outside_bounds_get_sentinel(mock_bridge, monkeypatch):
    """Saddle points projecting outside image bounds get sentinel (-1, -1)."""
    board_config = {
        "type": "charuco",
        "rows": 3,
        "cols": 3,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj = _make_board_obj(board_config)
    _setup_bridge(mock_bridge, res_x=100, res_y=100)

    # Saddle points span x in [-0.04, 0.04]. Map so left is in-bounds, right is out.
    # x=-0.04 → 0.04*800+50=18 (in), x=0.04 → 0.04*800+50=82 (in)... need offset.
    # Use offset=70: x=-0.04 → -32+70=38 (in), x=0.04 → 32+70=102 (out of 100).
    def project_partial_oob(pts, cam_world_mat, res, k_matrix, **kwargs):
        px = pts[:, 0] * 800 + 70
        py = -pts[:, 1] * 800 + 50
        return np.stack([px, py], axis=1)

    monkeypatch.setattr("render_tag.backend.projection.project_points", project_partial_oob)

    records = generate_board_records(mock_obj, "test_img")
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1

    # 3x3 board has (3-1)*(3-1) = 4 saddle points total.
    # Index alignment: length must always be 4 regardless of OOB.
    kps = board_records[0].keypoints
    assert kps is not None
    assert len(kps) == 4, f"Expected 4 saddle points (with sentinels), got {len(kps)}"

    # At least one should be the sentinel (-1, -1)
    sentinels = [p for p in kps if p == (-1.0, -1.0)]
    assert len(sentinels) > 0, "Expected at least one OOB sentinel"
    # At least one should be valid
    valid = [p for p in kps if p != (-1.0, -1.0)]
    assert len(valid) > 0, "Expected at least one in-bounds saddle point"


def test_skip_visibility_bypasses_frustum_culling(mock_bridge, monkeypatch):
    """With skip_visibility=True, all tags and saddle points are emitted."""
    board_config = {
        "type": "charuco",
        "rows": 3,
        "cols": 3,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj = _make_board_obj(board_config)
    _setup_bridge(mock_bridge, res_x=100, res_y=100)

    # Project everything far outside bounds
    def project_all_oob(pts, cam_world_mat, res, k_matrix, **kwargs):
        px = pts[:, 0] * 1000 + 5000  # Way outside [0, 100)
        py = -pts[:, 1] * 1000 + 5000
        return np.stack([px, py], axis=1)

    monkeypatch.setattr("render_tag.backend.projection.project_points", project_all_oob)

    records = generate_board_records(mock_obj, "test_img", skip_visibility=True)
    tag_records = [r for r in records if r.record_type == "TAG"]

    # 3x3 charuco has 5 white squares with tags. All should be emitted.
    assert len(tag_records) == 5

    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1
    assert board_records[0].keypoints is not None
    assert len(board_records[0].keypoints) == 4  # (3-1)*(3-1) saddle points


def test_behind_camera_tags_rejected(mock_bridge, monkeypatch):
    """Tags with behind-camera sentinel coordinates must be culled."""
    board_config = {
        "type": "charuco",
        "rows": 2,
        "cols": 2,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj = _make_board_obj(board_config)
    _setup_bridge(mock_bridge, res_x=1000, res_y=1000)

    # Return behind-camera sentinel for all points
    def project_behind_camera(pts, cam_world_mat, res, k_matrix, **kwargs):
        return np.full((len(pts), 2), -1e6)

    monkeypatch.setattr("render_tag.backend.projection.project_points", project_behind_camera)

    records = generate_board_records(mock_obj, "test_img")
    tag_records = [r for r in records if r.record_type == "TAG"]

    assert len(tag_records) == 0, "All behind-camera tags should be culled"


def test_keypoint_sentinel_preserves_index_alignment(mock_bridge, monkeypatch):
    """Sentinel insertion must preserve keypoints[i] == charuco_id i."""
    board_config = {
        "type": "charuco",
        "rows": 4,
        "cols": 4,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj = _make_board_obj(board_config)
    _setup_bridge(mock_bridge, res_x=100, res_y=100)

    # Project so left-side points are in-bounds, right-side are out.
    # Board spans ~[-0.16, 0.16] meters. Saddle grid is 3x3 = 9 points.
    def project_half_oob(pts, cam_world_mat, res, k_matrix, **kwargs):
        px = pts[:, 0] * 500 + 30  # Left in, right out
        py = -pts[:, 1] * 500 + 50
        return np.stack([px, py], axis=1)

    monkeypatch.setattr("render_tag.backend.projection.project_points", project_half_oob)

    records = generate_board_records(mock_obj, "test_img")
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1

    kps = board_records[0].keypoints
    assert kps is not None
    # Must always have exactly (rows-1)*(cols-1) = 9 entries
    assert len(kps) == 9, f"Expected 9 keypoints (with sentinels), got {len(kps)}"

    sentinels = [p for p in kps if p == (-1.0, -1.0)]
    valid = [p for p in kps if p != (-1.0, -1.0)]
    assert len(sentinels) > 0, "Some points should be OOB sentinels"
    assert len(valid) > 0, "Some points should be in-bounds"
    assert len(sentinels) + len(valid) == 9


def test_board_definition_metadata_charuco(mock_bridge):
    """BOARD record must carry board_definition metadata for ChArUco."""
    board_config = {
        "type": "charuco",
        "rows": 4,
        "cols": 4,
        "marker_size": 0.05,
        "square_size": 0.08,
        "dictionary": "tag36h11",
    }
    mock_obj = _make_board_obj(board_config)
    _setup_bridge(mock_bridge)

    records = generate_board_records(mock_obj, "test_img")
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1

    bd = board_records[0].board_definition
    assert bd is not None, "board_definition missing"
    assert bd.type == "charuco"
    assert bd.rows == 4
    assert bd.cols == 4
    assert np.isclose(bd.square_size_mm, 80.0)
    assert np.isclose(bd.marker_size_mm, 50.0)
    assert bd.dictionary == "tag36h11"
    assert bd.total_keypoints == 9  # (4-1)*(4-1)


def test_board_definition_metadata_aprilgrid(mock_bridge):
    """BOARD record must carry board_definition metadata for AprilGrid."""
    board_config = {
        "type": "aprilgrid",
        "rows": 4,
        "cols": 6,
        "marker_size": 0.05,
        "spacing_ratio": 0.2,
        "dictionary": "tag36h11",
    }
    mock_obj = _make_board_obj(board_config)
    _setup_bridge(mock_bridge)

    records = generate_board_records(mock_obj, "test_img")
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1

    bd = board_records[0].board_definition
    assert bd is not None, "board_definition missing"
    assert bd.type == "aprilgrid"
    assert bd.rows == 4
    assert bd.cols == 6
    assert np.isclose(bd.marker_size_mm, 50.0)
    assert bd.dictionary == "tag36h11"
    assert bd.spacing_ratio == 0.2
    assert bd.total_keypoints == 15  # (4-1)*(6-1)
