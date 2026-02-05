"""
Pure-Python geometry math for tag projection and metadata calculation.
No Blender dependencies.
"""

from __future__ import annotations

import numpy as np


def calculate_distance(point1: np.ndarray, point2: np.ndarray) -> float:
    """Calculates Euclidean distance between two 3D points."""
    return float(np.linalg.norm(point1 - point2))

def calculate_angle_of_incidence(
    target_location: np.ndarray,
    target_normal: np.ndarray,
    camera_location: np.ndarray
) -> float:
    """
    Calculates the angle of incidence (in degrees) between a target surface and a camera.
    
    Args:
        target_location: 3D position of the target.
        target_normal: 3D normal vector of the target surface (world space).
        camera_location: 3D position of the camera.
    """
    # Normalize normal
    norm = np.linalg.norm(target_normal)
    if norm < 1e-10:
        return 0.0
    normal = target_normal / norm
    
    # Vector from target to camera
    to_cam = camera_location - target_location
    to_cam_norm = np.linalg.norm(to_cam)
    if to_cam_norm < 1e-10:
        return 0.0
    to_cam /= to_cam_norm
    
    # Cosine of angle is dot product
    cos_theta = np.clip(np.dot(normal, to_cam), -1.0, 1.0)
    angle_rad = np.arccos(cos_theta)
    return float(np.degrees(angle_rad))

def get_opencv_camera_matrix(blender_matrix: np.ndarray) -> np.ndarray:
    """
    Converts a 4x4 Blender Camera-to-World matrix to OpenCV convention.
    
    Blender: right=X, up=Y, forward=-Z
    OpenCV: right=X, down=Y, forward=Z
    """
    flip_mat = np.array([
        [1, 0, 0, 0],
        [0, -1, 0, 0],
        [0, 0, -1, 0],
        [0, 0, 0, 1]
    ])
    return blender_matrix @ flip_mat

def get_world_normal(
    world_matrix: np.ndarray, local_normal: np.ndarray | None = None
) -> np.ndarray:
    """
    Transforms a local normal vector to world space using a 4x4 transformation matrix.
    """
    if local_normal is None:
        local_normal = np.array([0, 0, 1, 0]) # Default Z-up
        
    world_normal = (world_matrix @ local_normal)[:3]
    norm = np.linalg.norm(world_normal)
    if norm < 1e-10:
        return np.array([0.0, 0.0, 1.0])
    return world_normal / norm