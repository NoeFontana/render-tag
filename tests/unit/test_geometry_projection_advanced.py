"""
Advanced tests for projection math and coordinate transformations.
"""

import numpy as np
import pytest

from render_tag.geometry.projection_math import (
    get_opencv_camera_matrix,
    get_world_normal,
    calculate_angle_of_incidence,
)


def test_camera_matrix_conversion():
    # Identity matrix (Camera at origin, looking at -Z, Up is Y)
    blender_cam_to_world = np.eye(4)
    
    opencv_mat = get_opencv_camera_matrix(blender_cam_to_world)
    
    # In OpenCV, camera looks at +Z
    # So if blender_cam is identity, its -Z axis is world -Z.
    # The conversion flips Y and Z.
    # OpenCV Forward (Z) should now be World -Z
    # OpenCV Down (Y) should now be World -Y
    
    expected = np.array([
        [1,  0,  0, 0],
        [0, -1,  0, 0],
        [0,  0, -1, 0],
        [0,  0,  0, 1]
    ])
    assert np.allclose(opencv_mat, expected)


def test_get_world_normal():
    # Rotate 90 degrees around X (Y becomes Z)
    theta = np.radians(90)
    c, s = np.cos(theta), np.sin(theta)
    rot_x = np.array([
        [1, 0, 0, 0],
        [0, c, -s, 0],
        [0, s, c, 0],
        [0, 0, 0, 1]
    ])
    
    # Local normal [0, 0, 1]
    world_n = get_world_normal(rot_x)
    # [0, 0, 1] rotated 90 deg around X should be [0, -1, 0]
    assert np.allclose(world_n, [0, -1, 0])


def test_angle_of_incidence_edge_cases():
    target_pos = np.array([0, 0, 0])
    target_normal = np.array([0, 0, 1])
    
    # 1. Directly above (0 degrees)
    cam_pos = np.array([0, 0, 10])
    assert np.allclose(calculate_angle_of_incidence(target_pos, target_normal, cam_pos), 0.0)
    
    # 2. Grazing angle (90 degrees)
    cam_pos = np.array([10, 0, 0])
    assert np.allclose(calculate_angle_of_incidence(target_pos, target_normal, cam_pos), 90.0)
    
    # 3. Behind the surface (180 degrees or > 90)
    cam_pos = np.array([0, 0, -10])
    assert calculate_angle_of_incidence(target_pos, target_normal, cam_pos) > 90.0
    assert np.allclose(calculate_angle_of_incidence(target_pos, target_normal, cam_pos), 180.0)
