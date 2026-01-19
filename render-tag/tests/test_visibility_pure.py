"""
Unit tests for visibility_geometry module.
"""

from __future__ import annotations

import numpy as np
import pytest
from render_tag.visibility_geometry import (
    is_facing_camera,
    project_points,
    validate_visibility_metrics,
)


def test_is_facing_camera():
    tag_pos = np.array([0, 0, 0])
    tag_normal = np.array([0, 0, 1])  # Facing +Z
    
    # Camera at +Z (looking down at origin) -> Facing
    cam_pos = np.array([0, 0, 1])
    assert is_facing_camera(tag_pos, tag_normal, cam_pos) is True
    
    # Camera at -Z (looking up at origin) -> Not facing (flipped)
    cam_pos = np.array([0, 0, -1])
    assert is_facing_camera(tag_pos, tag_normal, cam_pos) is False
    
    # Camera at 45 degree angle
    cam_pos = np.array([1, 0, 1])
    # dot product is cos(45) = 0.707 > 0.15
    assert is_facing_camera(tag_pos, tag_normal, cam_pos) is True
    
    # Camera at 85 degree angle
    # cos(85) = 0.087 < 0.15
    cam_pos = np.array([np.tan(np.radians(85)), 0, 1])
    assert is_facing_camera(tag_pos, tag_normal, cam_pos, min_dot=0.15) is False


def test_project_points_basic():
    # Camera at (0, 0, 1) looking at origin (0, 0, 0)
    # Forward is (0, 0, -1)
    cam_pos = np.array([0, 0, 1])
    cam_rot = np.eye(3) # This is a bit simplified, but let's test a point on axis
    # In my look_at_rotation, forward (0,0,-1) with up (0,0,1) handled:
    from render_tag.math_utils import look_at_rotation, make_transformation_matrix
    R = look_at_rotation(np.array([0, 0, -1]))
    cam2world = make_transformation_matrix(cam_pos, R)
    
    # Simple intrinsics: 100 f, 320 cx, 240 cy
    K = np.array([[100, 0, 320], [0, 100, 240], [0, 0, 1]])
    
    # Point at origin
    pts = np.array([[0, 0, 0]])
    coords = project_points(pts, K, cam2world)
    
    # Point at origin is 1 unit in front of camera at (0,0,1)
    # In camera space it should be at (0, 0, 1) (if camera Z is forward)
    # Or (0, 0, -1) (if camera -Z is forward)
    # My project_points uses inverse(cam2world), so points_cam = R^T (P - C)
    # P-C = (0,0,0) - (0,0,1) = (0,0,-1)
    # R^T (0,0,-1) -> should be on camera Z axis
    
    assert coords.shape == (1, 2)
    assert coords[0, 0] == pytest.approx(320.0)
    assert coords[0, 1] == pytest.approx(240.0)


def test_validate_visibility_metrics():
    # unit square in image center
    corners = np.array([[310, 230], [330, 230], [330, 250], [310, 250]])
    width, height = 640, 480
    
    is_vis, metrics = validate_visibility_metrics(corners, width, height, min_area_pixels=100)
    assert is_vis is True
    assert metrics["area"] == pytest.approx(400.0)
    assert metrics["visible_corners"] == 4
    
    # Half out-of-bounds
    corners_off = np.array([[-10, 230], [10, 230], [10, 250], [-10, 250]])
    is_vis, metrics = validate_visibility_metrics(corners_off, width, height, min_visible_corners=4)
    assert is_vis is False
    assert metrics["visible_corners"] == 2
