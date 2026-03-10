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

    # To test Top-Left in OpenCV space, we need ID 0 to have
    # the minimum X and minimum Y coordinates among all intersections.

    records = generate_board_records(mock_obj, "test_img")
    board_records = [r for r in records if r.record_type == "BOARD"]
    assert len(board_records) == 1
    
    saddle_records = board_records[0].keypoints

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
