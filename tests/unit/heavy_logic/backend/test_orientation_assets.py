"""
Tests for 3D-Anchored Orientation Contract in asset generation.
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock

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
    def mock_set(key, val): props[key] = val
    def mock_get(key, default=None): return props.get(key, default)
    
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
    bridge, mock_obj, props = mock_bridge
    
    size = 0.1
    tag_family = "tag36h11"
    
    # Execute
    plane = create_tag_plane(
        size_meters=size,
        texture_path=None,
        tag_family=tag_family,
        margin_bits=0
    )
    
    # Verify keypoints_3d exists and has 4 points
    assert "keypoints_3d" in props
    kps = props["keypoints_3d"]
    assert len(kps) == 4
    
    # PLANE primitive is centered at 0,0. 
    # With size 0.1 and margin 0, corners should be at +/- 0.05
    half = size / 2.0
    
    # Contract: TL, TR, BR, BL
    # Logical Space (Z-up, Y-forward):
    # TL: (-half, half, 0)
    # TR: (half, half, 0)
    # BR: (half, -half, 0)
    # BL: (-half, -half, 0)
    
    expected = [
        [-half, half, 0.0],  # TL
        [half, half, 0.0],   # TR
        [half, -half, 0.0],  # BR
        [-half, -half, 0.0]  # BL
    ]
    
    for i in range(4):
        for j in range(3):
            assert pytest.approx(kps[i][j]) == expected[i][j]

def test_get_corner_world_coords_uses_keypoints_3d(mock_bridge):
    """Verify that get_corner_world_coords prefers keypoints_3d."""
    bridge, mock_obj, props = mock_bridge
    
    # Setup custom keypoints
    custom_kps = [
        [1.0, 1.0, 0.0],
        [2.0, 1.0, 0.0],
        [2.0, 2.0, 0.0],
        [1.0, 2.0, 0.0]
    ]
    props["keypoints_3d"] = custom_kps
    
    # Mock world matrix (Identity)
    # BlenderProc uses numpy for matrices
    import numpy as np
    mock_obj.get_local2world_mat.return_value = np.eye(4)
    bridge.np = np
    
    # Execute
    world_coords = get_corner_world_coords(mock_obj)
    
    # Verify
    assert world_coords == custom_kps
