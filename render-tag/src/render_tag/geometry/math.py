"""
Shared mathematical utilities for render-tag.

Pure-Python/NumPy implementations of geometry and projection primitives.
No Blender dependencies.
"""

from __future__ import annotations

import numpy as np


def compute_polygon_area(points: np.ndarray) -> float:
    """Compute the area of a 2D polygon using the shoelace formula.

    Args:
        points: (N, 2) array of vertex coordinates.

    Returns:
        Area of the polygon.
    """
    if len(points) < 3:
        return 0.0

    x = points[:, 0]
    y = points[:, 1]

    # Shoelace formula: 0.5 * |sum(x_i * y_{i+1} - x_{i+1} * y_i)|
    area = 0.5 * np.abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    return float(area)


def make_transformation_matrix(
    translation: np.ndarray | list[float],
    rotation_matrix: np.ndarray,
) -> np.ndarray:
    """Build a 4x4 transformation matrix from translation and rotation.

    Args:
        translation: (3,) translation vector.
        rotation_matrix: (3, 3) rotation matrix.

    Returns:
        (4, 4) transformation matrix.
    """
    mat = np.eye(4)
    mat[:3, :3] = rotation_matrix
    mat[:3, 3] = translation
    return mat


def rotation_matrix_from_vectors(vec1: np.ndarray, vec2: np.ndarray) -> np.ndarray:
    """Find the rotation matrix that aligns vec1 to vec2.

    Args:
        vec1: Source vector.
        vec2: Target vector.

    Returns:
        (3, 3) rotation matrix.
    """
    a, b = (
        (vec1 / np.linalg.norm(vec1)).reshape(3),
        (vec2 / np.linalg.norm(vec2)).reshape(3),
    )
    v = np.cross(a, b)
    c = np.dot(a, b)
    s = np.linalg.norm(v)

    if s < 1e-10:
        # Already aligned or opposite
        if c > 0:
            return np.eye(3)
        else:
            # 180 degree rotation around any orthogonal vector
            # Find an orthogonal vector
            ortho = np.array([1, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1, 0])
            v_ortho = np.cross(a, ortho)
            v_ortho /= np.linalg.norm(v_ortho)
            # Rodrigues rotation for 180 degrees
            k = v_ortho
            K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
            return np.eye(3) + 2 * (K @ K)

    kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    rotation_matrix = np.eye(3) + kmat + kmat.dot(kmat) * ((1 - c) / (s**2))
    return rotation_matrix


def look_at_rotation(
    forward_vec: np.ndarray, up_vec: np.ndarray = np.array([0, 0, 1])
) -> np.ndarray:
    """Compute a rotation matrix from a forward vector and an up vector.

    This matches the behavior of bproc.camera.rotation_from_forward_vec.
    The camera's local forward is -Z, up is Y.

    Args:
        forward_vec: Direction the camera should face.
        up_vec: World up vector.

    Returns:
        (3, 3) rotation matrix.
    """
    # Normalize forward vector
    f = forward_vec / np.linalg.norm(forward_vec)

    # Handle degenerate case where forward is parallel to up
    if abs(np.dot(f, up_vec)) > 0.999:
        # Use a different up vector
        up_vec = np.array([0, 1, 0]) if abs(f[1]) < 0.999 else np.array([1, 0, 0])

    # Standard Gram-Schmidt or similar to find axes
    # In BlenderProc/OpenCV, Z is usually forward (or -Z)
    # Blender camera: forward is -Z, up is Y, right is X
    # BlenderProc's rotation_from_forward_vec maps world forward to camera -Z

    # Camera axes in world coordinates
    # cam_z = -f (forward is -Z)
    z_axis = -f
    # cam_x = up x cam_z (right is X)
    x_axis = np.cross(up_vec, z_axis)
    x_axis /= np.linalg.norm(x_axis)
    # cam_y = cam_z x cam_x (up is Y)
    y_axis = np.cross(z_axis, x_axis)

    # Rotation matrix columns are the world-space axes
    R = np.stack([x_axis, y_axis, z_axis], axis=1)
    return R
