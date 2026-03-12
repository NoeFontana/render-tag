"""
Tests for 3D-Anchored Orientation Contract in asset generation.
"""

from unittest.mock import MagicMock

import pytest

from render_tag.backend.assets import create_tag_plane, get_corner_world_coords


@pytest.fixture
def mock_bridge(monkeypatch):
    """Mock BlenderBridge for unit testing without Blender."""
    mock = MagicMock()
    # Mock bproc.object.create_primitive
    mock_obj = MagicMock()

    # Internal blender_obj mock
    blender_obj = MagicMock()
    blender_obj.__getitem__ = lambda self, key: blender_obj.get(key)
    blender_obj.__setitem__ = lambda self, key, value: blender_obj.set(key, value)

    # Store custom properties in a dict for verification
    props = {}

    def mock_set(key, val):
        props[key] = val

    def mock_get(key, default=None):
        return props.get(key, default)

    blender_obj.get = mock_get
    blender_obj.set = mock_set
    # Also handle dict-like access for mock
    blender_obj.__getitem__.side_effect = lambda key: props[key]
    blender_obj.__setitem__.side_effect = mock_set

    mock_obj.blender_obj = blender_obj
    mock.bproc.object.create_primitive.return_value = mock_obj

    monkeypatch.setattr("render_tag.backend.assets.bridge", mock)
    monkeypatch.setattr("render_tag.backend.assets.global_pool.get_tag", lambda: mock_obj)
    return mock, mock_obj, props


def test_create_tag_plane_assigns_keypoints_3d(mock_bridge):
    """Verify that create_tag_plane assigns keypoints_3d custom property."""
    _bridge, _mock_obj, props = mock_bridge

    size = 0.1
    tag_family = "tag36h11"

    # Execute
    create_tag_plane(size_meters=size, texture_path=None, tag_family=tag_family, margin_bits=0)

    # Verify keypoints_3d exists and has 4 points
    assert "keypoints_3d" in props
    kps = props["keypoints_3d"]
    assert len(kps) == 4

    # PLANE primitive is centered at 0,0.
    # With size 0.1 and margin 0, local corners should be at +/- 1.0
    # because the plane is 2x2.
    half = 1.0

    # Contract: TL, TR, BR, BL
    # Logical Space (Z-up, Y-forward):
    # TL: (-half, half, 0)
    # TR: (half, half, 0)
    # BR: (half, -half, 0)
    # BL: (-half, -half, 0)

    expected = [
        [-half, half, 0.0],  # TL
        [half, half, 0.0],  # TR
        [half, -half, 0.0],  # BR
        [-half, -half, 0.0],  # BL
    ]

    for i in range(4):
        for j in range(3):
            assert pytest.approx(kps[i][j]) == expected[i][j]


def test_get_corner_world_coords_uses_keypoints_3d(mock_bridge):
    """Verify that get_corner_world_coords prefers keypoints_3d."""
    bridge, mock_obj, _props = mock_bridge

    # Setup custom keypoints
    custom_kps = [[1.0, 1.0, 0.0], [2.0, 1.0, 0.0], [2.0, 2.0, 0.0], [1.0, 2.0, 0.0]]
    _props["keypoints_3d"] = custom_kps

    # Mock world matrix (Identity)
    # BlenderProc uses numpy for matrices
    import numpy as np

    mock_obj.get_local2world_mat.return_value = np.eye(4)
    bridge.np = np

    # Execute
    world_coords = get_corner_world_coords(mock_obj)

    # Verify
    assert world_coords == custom_kps


def test_get_corner_world_coords_with_scaling(mock_bridge):
    """Verify that get_corner_world_coords handles scaling correctly.

    If keypoints_3d are in local space (e.g. +/- 1.0 for a 2x2 plane),
    and the world matrix has a scale of 0.05 (for a 0.1m tag),
    the world coordinates should be +/- 0.05.
    """
    bridge, mock_obj, _props = mock_bridge
    import numpy as np

    bridge.np = np

    # 1. Setup local keypoints (Normalized to +/- 1.0 for a 2x2 plane)
    local_kps = [[-1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, -1.0, 0.0], [-1.0, -1.0, 0.0]]
    _props["keypoints_3d"] = local_kps

    # 2. Setup world matrix with scale 0.05 (size 0.1m) and a translation
    size = 0.1
    scale = size / 2.0
    world_mat = np.eye(4)
    world_mat[0, 0] = scale
    world_mat[1, 1] = scale
    world_mat[0, 3] = 10.0  # Translate by 10m in X
    mock_obj.get_local2world_mat.return_value = world_mat

    # 3. Execute
    world_coords = get_corner_world_coords(mock_obj)

    # 4. Verify
    # Expected: 10.0 +/- 0.05
    expected = [[9.95, 0.05, 0.0], [10.05, 0.05, 0.0], [10.05, -0.05, 0.0], [9.95, -0.05, 0.0]]

    for i in range(4):
        for j in range(3):
            assert pytest.approx(world_coords[i][j]) == expected[i][j]


def test_integrated_tag_creation_and_projection(mock_bridge):
    """Verify the full lifecycle of tag creation and world-coordinate extraction.

    This test is CRITICAL as it mimics the actual backend execution flow.
    """
    bridge, mock_obj, _props = mock_bridge
    import numpy as np

    bridge.np = np

    # 1. Create a tag (0.2m size)
    # The user reported 10x error for a tag (42 vs 424 pixels).
    # If size=0.2m, then scale=0.1.
    size = 0.2
    create_tag_plane(size_meters=size, texture_path=None, tag_family="tag36h11")

    # 2. Setup world matrix with scale size/2 (as BlenderProc does for the object)
    scale = size / 2.0  # 0.1
    world_mat = np.eye(4)
    world_mat[0, 0] = scale
    world_mat[1, 1] = scale
    # Position doesn't matter for the factor error, but let's put it somewhere
    world_mat[:3, 3] = [1.0, 1.0, 1.0]
    mock_obj.get_local2world_mat.return_value = world_mat

    # 3. Extract world coordinates
    world_coords = get_corner_world_coords(mock_obj)

    # 4. Verify
    # Correct result should be 1.0 +/- 0.1 (total width 0.2m)
    # Broken result will be 1.0 +/- 0.01 (total width 0.02m)
    expected_half = size / 2.0  # 0.1
    expected = [
        [1.0 - expected_half, 1.0 + expected_half, 1.0],
        [1.0 + expected_half, 1.0 + expected_half, 1.0],
        [1.0 + expected_half, 1.0 - expected_half, 1.0],
        [1.0 - expected_half, 1.0 - expected_half, 1.0],
    ]

    for i in range(4):
        for j in range(3):
            # If this is broken, it will find 0.99 instead of 0.9 (for 1.0 - 0.1)
            assert pytest.approx(world_coords[i][j]) == expected[i][j]
