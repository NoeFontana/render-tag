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
    def mock_project(pts, cam_world_mat, res, k_matrix):
        px = pts[:, 0]
        py = -pts[:, 1]  # Flip Y
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

    # Filter for saddle points
    saddle_records = [r for r in records if r.record_type == "CHARUCO_SADDLE"]

    assert len(saddle_records) == 9
    ids = sorted([r.tag_id for r in saddle_records])

    # Should be continuous 0 to 8
    assert ids == list(range(9))


def test_charuco_indexing_layout(mock_bridge):
    """
    Verify row-major physical ordering for ChArUco.
    ID 0 should be Top-Left physically (smallest X, smallest Y in OpenCV).
    ID 1 should be directly to its right.
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

    # To test Top-Left in OpenCV space, we need ID 0 to have
    # the minimum X and minimum Y coordinates among all intersections.

    records = generate_board_records(mock_obj, "test_img")
    saddle_records = {r.tag_id: r.corners[0] for r in records if r.record_type == "CHARUCO_SADDLE"}

    # ID 0 should exist if fixed
    assert 0 in saddle_records

    p0 = saddle_records[0]
    for other_id, p_other in saddle_records.items():
        if other_id == 0:
            continue
        # Row-major: scanning left-to-right, then top-to-bottom.
        # ID 0 is top-leftmost.
        # In Y-down, top means smaller Y. Left means smaller X.
        assert p0[1] <= p_other[1]  # ID 0 Y <= any other Y (it's in first row)
        if p0[1] == p_other[1]:
            assert p0[0] < p_other[0]  # In same row, ID 0 is leftmost


def test_aprilgrid_intersection_deprecation(mock_bridge):
    """
    Verify AprilGrid does not output global intersections.
    It should only output tag corners.
    """
    mock_obj = MagicMock()
    board_config = {
        "type": "aprilgrid",
        "rows": 4,
        "cols": 4,
        "marker_size": 0.05,
        "spacing_ratio": 0.2,
        "dictionary": "tag36h11",
    }
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {"board": board_config}.get(
        key, default
    )

    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = [0, 0, 0]
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 10]

    records = generate_board_records(mock_obj, "test_img")

    # Should NOT have any record_type == "APRILGRID_CORNER" (global intersections)
    intersection_records = [r for r in records if r.record_type == "APRILGRID_CORNER"]
    assert len(intersection_records) == 0


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

    # Simulate a Blender object that has a 0.1 scale and a simple translation
    scaled_world_matrix = np.array(
        [
            [0.1, 0.0, 0.0, 1.0],
            [0.0, 0.1, 0.0, 2.0],
            [0.0, 0.0, 0.1, 3.0],
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

    def mock_project_points(pts, *args):
        projected_pts.extend(pts)
        return [[float(p[0]), float(-p[1])] for p in pts]

    mock_bridge.project_points = mock_project_points
    # Mocking in the module using it:
    import render_tag.backend.projection

    render_tag.backend.projection.project_points = mock_project_points

    records = generate_board_records(mock_obj, "test_scale_img")

    # We should have two tag records (since charuco 2x2 has 2
    # white squares with tags: (0,0) and (1,1))
    tag_records = [r for r in records if r.record_type == "TAG"]
    assert len(tag_records) == 2

    # The projected_pts passed to project_points should have standard physical size
    # Width of the marker in 3D without the 0.1 object scale should be 0.1m.
    # We check the world width (distance between TL and TR).
    assert len(projected_pts) >= 4
    # The first 4 points should be the corners of the single tag
    tl, tr, _, _ = projected_pts[:4]

    # Since world_matrix now PRESERVES scale, width in 3D should be
    # marker_size * scale (0.1 * 0.1 = 0.01)
    diff = np.array(tr) - np.array(tl)
    width_3d = np.linalg.norm(diff)

    assert np.isclose(width_3d, 0.01), f"Expected marker 3D width 0.01, got {width_3d}"
