import numpy as np
import pytest
from render_tag.generation.projection_math import get_opencv_camera_matrix, calculate_relative_pose, matrix_to_quaternion_wxyz

def test_opencv_camera_matrix_determinant():
    """
    Test that the current get_opencv_camera_matrix implementation 
    flips the determinant to -1 (incorrect for rigid transforms).
    """
    # Simple identity camera matrix (at origin, looking along -Z)
    blender_cam_matrix = np.eye(4)
    
    # Current implementation
    opencv_cam_matrix = get_opencv_camera_matrix(blender_cam_matrix)
    
    det = np.linalg.det(opencv_cam_matrix[:3, :3])
    
    # Restored logic uses 180 deg rotation, so det must be +1
    assert np.isclose(det, 1.0), f"Determinant is {det}, expected 1.0"

def test_project_point_at_origin():
    """
    Test that a point at the world origin is correctly projected 
    when the camera is at (0, 0, 10) looking at it.
    In OpenCV space, it should have Z = 10.
    """
    # Camera at (0, 0, 10), Identity rotation (looking at -Z in Blender)
    blender_cam_matrix = np.eye(4)
    blender_cam_matrix[:3, 3] = [0, 0, 10]
    
    # K matrix: fx=fy=500, cx=320, cy=240
    k_matrix = np.array([[500, 0, 320], [0, 500, 240], [0, 0, 1]])
    
    # Point at origin
    points_world = np.array([[0.0, 0.0, 0.0]])
    
    # Manual projection steps (matching project_points)
    from render_tag.generation.projection_math import project_points
    pixels = project_points(points_world, blender_cam_matrix, [640, 480], k_matrix)
    
    # Expected: 
    # world_to_cam = inv(diag(1, -1, -1) with t=[0,0,10])
    # world_to_cam = diag(1, -1, -1) with t=[0,0,10]
    # p_cam = world_to_cam @ [0,0,0,1] = [0, 0, 10, 1]
    # x_px = 0 * 500 / 10 + 320 = 320
    # y_px = 0 * 500 / 10 + 240 = 240
    
    assert pixels[0, 0] == pytest.approx(320.0)
    assert pixels[0, 1] == pytest.approx(240.0)
