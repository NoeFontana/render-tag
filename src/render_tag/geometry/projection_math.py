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
    target_location: np.ndarray, target_normal: np.ndarray, camera_location: np.ndarray
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
    to_cam = (camera_location - target_location).astype(np.float64)
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
    flip_mat = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    return blender_matrix @ flip_mat


def get_world_normal(
    world_matrix: np.ndarray, local_normal: np.ndarray | None = None
) -> np.ndarray:
    """
    Transforms a local normal vector to world space using a 4x4 transformation matrix.
    """
    if local_normal is None:
        local_normal = np.array([0, 0, 1, 0])  # Default Z-up

    world_normal = (world_matrix @ local_normal)[:3]
    norm = np.linalg.norm(world_normal)
    if norm < 1e-10:
        return np.array([0.0, 0.0, 1.0])
    return world_normal / norm


def matrix_to_quaternion_wxyz(matrix: np.ndarray) -> list[float]:
    """Convert a 4x4 or 3x3 rotation matrix to a scalar-first unit quaternion [w, x, y, z].

    Uses a numerically stable algorithm (Shepperd's method) to avoid
    singularities.

    Args:
        matrix: 4x4 transformation matrix or 3x3 rotation matrix.

    Returns:
        List of 4 floats: [w, x, y, z].
    """
    m = np.asarray(matrix)[:3, :3]
    trace = np.trace(m)

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m[2, 1] - m[1, 2]) * s
        y = (m[0, 2] - m[2, 0]) * s
        z = (m[1, 0] - m[0, 1]) * s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s

    return [float(w), float(x), float(y), float(z)]


def calculate_relative_pose(
    tag_world_matrix: np.ndarray, blender_cam_world_matrix: np.ndarray
) -> dict[str, list[float]]:
    """
    Calculates the relative pose of a tag in OpenCV camera coordinates.

    Args:
        tag_world_matrix: 4x4 matrix (World-to-Tag)
        blender_cam_world_matrix: 4x4 matrix (Blender Camera-to-World)

    Returns:
        Dict with 'position' ([x, y, z]) and 'rotation_quaternion' ([w, x, y, z])
    """
    # 1. Convert Blender Cam to OpenCV Cam
    # OpenCV: Z forward, Y down, X right
    opencv_cam_world = get_opencv_camera_matrix(blender_cam_world_matrix)

    # 2. Invert to get World-to-Camera (OpenCV)
    world_to_opencv_cam = np.linalg.inv(opencv_cam_world)

    # 3. Relative transformation: T_cam_tag = T_world_to_cam * T_tag_in_world
    rel_mat = world_to_opencv_cam @ tag_world_matrix

    # 4. Extract position and quaternion
    pos = rel_mat[:3, 3].tolist()
    quat = matrix_to_quaternion_wxyz(rel_mat)

    return {
        "position": [float(p) for p in pos],
        "rotation_quaternion": quat,
    }
