"""
Tests for orientation preservation in the projection engine.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from render_tag.backend.projection import generate_subject_records


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
    monkeypatch.setattr(
        "render_tag.backend.projection.get_world_normal",
        lambda *args: np.array([0, 0, 1]),
    )
    monkeypatch.setattr(
        "render_tag.backend.projection.calculate_angle_of_incidence",
        lambda *args: 0.0,
    )
    monkeypatch.setattr(
        "render_tag.backend.projection.calculate_relative_pose",
        lambda *args: {"position": [0, 0, 0], "rotation_quaternion": [1, 0, 0, 0]},
    )

    return mock


def test_generate_subject_records_preserves_order(mock_bridge):
    """Verify that logical 3D order is preserved in 2D output."""
    bridge = mock_bridge

    # Setup mock object with keypoints in specific logical order
    # TL, TR, BR, BL (Clockwise in Y-down)
    logical_kps = [[10.0, 10.0, 0.0], [20.0, 10.0, 0.0], [20.0, 20.0, 0.0], [10.0, 20.0, 0.0]]

    mock_obj = MagicMock()
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {
        "keypoints_3d": logical_kps,
        "type": "TAG",
        "tag_id": 1,
        "tag_family": "tag36h11",
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


# --- Phase 2: 3D-to-2D Projection Anchor Tests (pure math, no Blender) ---


def _project_tl(tag_size_mm, position, rotation_quaternion, k_matrix):
    """Project the TL corner using the stored pose and K matrix."""
    from render_tag.generation.projection_math import quaternion_wxyz_to_matrix

    half = tag_size_mm / 2000.0  # mm → m, half-size
    local_tl = np.array([-half, -half, 0.0])  # Center-Origin, Y-down
    R = quaternion_wxyz_to_matrix(rotation_quaternion)
    t = np.array(position, dtype=float)
    p_cam = R @ local_tl + t

    k = np.array(k_matrix, dtype=float)
    x = k[0, 0] * p_cam[0] / p_cam[2] + k[0, 2]
    y = k[1, 1] * p_cam[1] / p_cam[2] + k[1, 2]
    return x, y


def test_anchor_projection_perfect_pose():
    """Projected TL must land sub-pixel on corners[0] when pose is exact."""
    # Tag at Z=1m, identity rotation, fx=fy=500, principal point=(320, 240)
    tag_size_mm = 160.0
    position = [0.0, 0.0, 1.0]
    rotation_quaternion = [1.0, 0.0, 0.0, 0.0]  # wxyz identity
    k_matrix = [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]

    x_proj, y_proj = _project_tl(tag_size_mm, position, rotation_quaternion, k_matrix)

    # half = 0.08m → projected offset = 500 * (-0.08) / 1 = -40px from principal point
    # TL expected at (320 - 40, 240 - 40) = (280, 200)
    corners_correct = [(280.0, 200.0), (360.0, 200.0), (360.0, 280.0), (280.0, 280.0)]

    dist0 = np.hypot(x_proj - corners_correct[0][0], y_proj - corners_correct[0][1])
    assert dist0 < 0.5, f"Anchor failed: dist_to_corner0={dist0:.3f}px"


def test_anchor_projection_detects_180_degree_error():
    """When corners[0] and corners[2] are swapped, projected TL lands on corners[2].

    This is the DictionaryOrientationError signature: the texture is 180° out of
    phase with the 3D geometry.
    """
    tag_size_mm = 160.0
    position = [0.0, 0.0, 1.0]
    rotation_quaternion = [1.0, 0.0, 0.0, 0.0]  # wxyz identity
    k_matrix = [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]

    x_proj, y_proj = _project_tl(tag_size_mm, position, rotation_quaternion, k_matrix)

    # corners with 180° index swap: BR at [0], TL at [2]
    corners_180 = [(360.0, 280.0), (280.0, 280.0), (280.0, 200.0), (360.0, 200.0)]

    dist0 = np.hypot(x_proj - corners_180[0][0], y_proj - corners_180[0][1])
    dist2 = np.hypot(x_proj - corners_180[2][0], y_proj - corners_180[2][1])

    assert dist0 > 10.0, f"Expected large dist to corners[0], got {dist0:.1f}px"
    assert dist2 < 0.5, f"Expected near-zero dist to corners[2], got {dist2:.3f}px"


def test_projection_engine_is_agnostic_to_visual_shuffling(mock_bridge, monkeypatch):
    """
    Verify that even if visual order is 'inverted', the logical
    payload order is strictly maintained.
    """
    bridge = mock_bridge

    # Logical order: TL, TR, BR, BL
    logical_kps = [[10.0, 10.0, 0.0], [20.0, 10.0, 0.0], [20.0, 20.0, 0.0], [10.0, 20.0, 0.0]]

    # Shuffled CW: TR, BR, BL, TL
    shuffled_coords = np.array([[20.0, 10.0], [20.0, 20.0], [10.0, 20.0], [10.0, 10.0]])
    monkeypatch.setattr(
        "render_tag.backend.projection.project_points", lambda *args: shuffled_coords
    )

    mock_obj = MagicMock()
    mock_obj.blender_obj.get.side_effect = lambda key, default=None: {
        "keypoints_3d": logical_kps,
        "type": "TAG",
        "tag_id": 1,
        "tag_family": "tag36h11",
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
