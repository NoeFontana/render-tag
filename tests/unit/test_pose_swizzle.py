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
    
    # THIS SHOULD FAIL (we want it to be +1, but current implementation makes it -1)
    # The current code uses a reflection matrix [1, -1, -1] which has det = -1
    assert det > 0, f"Determinant is {det}, expected > 0"

def test_relative_pose_quaternion_validity():
    """
    Test that the current implementation yields invalid/unnormalized quaternions 
    due to the reflection matrix.
    """
    tag_world_matrix = np.eye(4)
    blender_cam_world_matrix = np.eye(4)
    blender_cam_world_matrix[:3, 3] = [0, 0, 1] # Camera at (0,0,1)
    
    pose = calculate_relative_pose(tag_world_matrix, blender_cam_world_matrix)
    quat = pose["rotation_quaternion"]
    
    # Check if quaternion is normalized (w^2 + x^2 + y^2 + z^2 = 1)
    norm_sq = sum(c*c for c in quat)
    
    # THIS SHOULD FAIL if the matrix has det = -1, as matrix_to_quaternion_wxyz 
    # expects a pure rotation matrix.
    assert np.isclose(norm_sq, 1.0, atol=1e-5), f"Quaternion is not normalized: norm_sq={norm_sq}"
