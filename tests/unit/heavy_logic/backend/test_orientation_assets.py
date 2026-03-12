"""
Tests for 3D-Anchored Orientation Contract in asset generation.
"""

from unittest.mock import MagicMock

import pytest

from render_tag.backend.assets import create_tag_plane, get_corner_world_coords


class MockVertex:
    def __init__(self, co):
        self.co = list(co)


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

    # Mock Blender mesh data for vertex manipulation
    # A standard Blender PLANE primitive is 2x2 centered at 0,0
    mock_data = MagicMock()
    mock_data.vertices = [
        MockVertex([-1.0, -1.0, 0.0]),
        MockVertex([1.0, -1.0, 0.0]),
        MockVertex([-1.0, 1.0, 0.0]),
        MockVertex([1.0, 1.0, 0.0]),
    ]
    blender_obj.data = mock_data

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


def test_create_tag_plane_mesh_boundary():
    """Verify that the resulting 3D mesh vertices do not start at 0.0 and are offset correctly."""
    from render_tag.backend.assets import create_tag_plane

    size = 0.1  # marker_size_m
    tag_family = "tag36h11"
    margin_bits = 1

    # For tag36h11, grid_size = 8
    # offset_m = (0.1 / 8) * 1 = 0.0125

    mock_obj = MagicMock()
    blender_obj = MagicMock()

    mock_data = MagicMock()
    # A standard Blender PLANE primitive is 2x2 centered at 0,0
    mock_data.vertices = [
        MockVertex([-1.0, -1.0, 0.0]),
        MockVertex([1.0, -1.0, 0.0]),
        MockVertex([-1.0, 1.0, 0.0]),
        MockVertex([1.0, 1.0, 0.0]),
    ]
    blender_obj.data = mock_data
    mock_obj.blender_obj = blender_obj

    import render_tag.backend.assets as assets

    original_get_tag = assets.global_pool.get_tag
    assets.global_pool.get_tag = lambda: mock_obj

    try:
        # Note: the new contract expects size_meters to be marker_size_m
        create_tag_plane(
            size_meters=size, texture_path=None, tag_family=tag_family, margin_bits=margin_bits
        )

        vertices = mock_obj.blender_obj.data.vertices
        coords = [v.co for v in vertices]

        # We expect vertices to bound from [-offset_m, -offset_m]
        # to [marker_size_m + offset_m, marker_size_m + offset_m]
        offset_m = (size / 8) * margin_bits

        # The plane's min X and Y should be exactly -offset_m
        min_x = min(co[0] for co in coords)
        min_y = min(co[1] for co in coords)
        assert pytest.approx(min_x) == -offset_m
        assert pytest.approx(min_y) == -offset_m

        # The plane's max X and Y should be exactly size + offset_m
        max_x = max(co[0] for co in coords)
        max_y = max(co[1] for co in coords)
        assert pytest.approx(max_x) == size + offset_m
        assert pytest.approx(max_y) == size + offset_m

    finally:
        assets.global_pool.get_tag = original_get_tag


def test_create_tag_plane_assigns_keypoints_3d(mock_bridge):
    """Verify that create_tag_plane assigns keypoints_3d custom property."""
    _bridge, _mock_obj, props = mock_bridge

    size = 0.1
    tag_family = "tag36h11"

    # Execute
    # The plane vertices are populated via the mock.
    # Note: the new contract expects size_meters to be marker_size_m
    create_tag_plane(size_meters=size, texture_path=None, tag_family=tag_family, margin_bits=0)

    # Verify keypoints_3d exists and has 4 points
    assert "keypoints_3d" in props
    kps = props["keypoints_3d"]
    assert len(kps) == 4

    # Contract: TL, TR, BR, BL
    # Logical Space (OpenCV continuous coordinates):
    # TL: (0.0, 0.0, 0.0)
    # TR: (size, 0.0, 0.0)
    # BR: (size, size, 0.0)
    # BL: (0.0, size, 0.0)

    expected = [
        [0.0, 0.0, 0.0],  # TL
        [size, 0.0, 0.0],  # TR
        [size, size, 0.0],  # BR
        [0.0, size, 0.0],  # BL
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
    size = 0.2
    create_tag_plane(size_meters=size, texture_path=None, tag_family="tag36h11")

    # 2. Setup world matrix with scale 1.0 (size is baked into vertices now)
    scale = 1.0
    world_mat = np.eye(4)
    world_mat[0, 0] = scale
    world_mat[1, 1] = scale
    # Position
    world_mat[:3, 3] = [1.0, 1.0, 1.0]
    mock_obj.get_local2world_mat.return_value = world_mat

    # 3. Extract world coordinates
    world_coords = get_corner_world_coords(mock_obj)

    # 4. Verify
    # The local corners are [0,0], [size,0], [size,size], [0,size]
    # At position 1.0, 1.0, 1.0
    expected = [
        [1.0 + 0.0, 1.0 + 0.0, 1.0],
        [1.0 + size, 1.0 + 0.0, 1.0],
        [1.0 + size, 1.0 + size, 1.0],
        [1.0 + 0.0, 1.0 + size, 1.0],
    ]

    for i in range(4):
        for j in range(3):
            assert pytest.approx(world_coords[i][j]) == expected[i][j]
