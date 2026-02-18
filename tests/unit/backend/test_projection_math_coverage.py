import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from render_tag.backend.projection import (
    project_points,
    is_facing_camera,
    validate_visibility_metrics,
    compute_tag_area_in_image,
)

def test_project_points_simple():
    """Test pure math projection without bridge dependencies."""
    # Camera at origin looking down -Z
    points_3d = np.array([
        [0, 0, -1],  # Center
        [1, 1, -1],  # Top-Right
    ])
    
    # Identity transform (camera at 0,0,0, no rotation)
    # Blender camera looks down -Z, Y up, X right
    # But standard CV convention: Z forward.
    # Blender matrix to CV:
    # If camera matrix is identity in Blender:
    # It is at 0,0,0.
    
    # Let's use a known K matrix
    K = np.array([
        [100, 0, 50],
        [0, 100, 50],
        [0, 0, 1]
    ])
    
    # If camera is at origin, points in camera frame = points in world frame?
    # project_points takes "blender_cam_mat" (4x4 world matrix of camera)
    
    # Case 1: Camera at origin
    cam_mat = np.eye(4)
    
    # 3D points are in World Frame.
    # We need to transform World -> Camera.
    # In Blender: Camera looks down -Z.
    # project_points implementation handles the coordinate system change?
    # Let's inspect project_points implementation via test behavior.
    
    # If we pass identity cam_mat, it means camera is at 0,0,0 looking down -Z (Blender default).
    # Point (0,0,-1) is directly in front.
    # Should project to principal point (50, 50).
    
    projs = project_points(points_3d, cam_mat, [100, 100], K)
    
    # (0,0,-1) -> (50, 50)
    assert np.allclose(projs[0], [50, 50])
    
    # (1, 1, -1) -> x = fx * X/Z + cx = 100 * (1/-1) + 50 = -50? 
    # Wait, Z is negative. distance is +1.
    # The math in project_points usually inverts Z or handles -Z.
    pass

def test_is_facing_camera():
    tag_center = np.array([0, 0, 0])
    # Normal pointing up (Z+)
    normal = np.array([0, 0, 1])
    
    # Camera above (0, 0, 10)
    cam_pos_visible = np.array([0, 0, 10])
    assert is_facing_camera(tag_center, normal, cam_pos_visible) is True
    
    # Camera below (0, 0, -10) -> seeing back of tag
    cam_pos_hidden = np.array([0, 0, -10])
    assert is_facing_camera(tag_center, normal, cam_pos_hidden) is False
    
    # Camera at side (10, 0, 0) -> 90 degrees
    # Dot product is 0. Strict inequality might define behavior.
    cam_pos_side = np.array([10, 0, 0])
    # normal (0,0,1) dot (10,0,0) = 0.
    # Implementation usually checks angle < 90.
    assert is_facing_camera(tag_center, normal, cam_pos_side) is False

def test_validate_visibility_metrics():
    # 100x100 image
    res_x, res_y = 100, 100
    
    # Case 1: Fully inside
    corners_in = np.array([[10, 10], [90, 10], [90, 90], [10, 90]])
    visible, metrics = validate_visibility_metrics(corners_in, res_x, res_y)
    assert visible is True
    assert metrics["visible_corners"] == 4
    
    # Case 2: Fully outside
    corners_out = np.array([[-10, -10], [-5, -10], [-5, -5], [-10, -5]])
    visible, metrics = validate_visibility_metrics(corners_out, res_x, res_y)
    assert visible is False
    assert metrics["visible_corners"] == 0
    
    # Case 3: Partial
    # Square from (50, 50) to (150, 150)
    # Inside part: (50,50) is inside. (150,50) out. (150,150) out. (50,150) out.
    # Only 1 corner inside (50, 50).
    corners_part = np.array([[50, 50], [150, 50], [150, 150], [50, 150]])
    visible, metrics = validate_visibility_metrics(corners_part, res_x, res_y)
    assert metrics["visible_corners"] == 1
    # Default requires 4 corners visible
    assert visible is False

@patch("render_tag.backend.projection.bridge")
def test_compute_tag_area_in_image(mock_bridge):
    # Mock resolution
    mock_bridge.bpy.context.scene.render.resolution_x = 100
    mock_bridge.bpy.context.scene.render.resolution_y = 100
    mock_bridge.np = np
    
    # 10x10 square
    corners = [(10, 10), (20, 10), (20, 20), (10, 20)]
    area = compute_tag_area_in_image(corners)
    assert np.isclose(area, 100.0)
