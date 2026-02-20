"""
Camera geometry utilities for render-tag.

Handles camera pose sampling and validation without Blender dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from render_tag.generation.math import (
    look_at_rotation,
    make_transformation_matrix,
    rotation_matrix_from_vectors,
)


@dataclass
class CameraPose:
    """A camera pose in world coordinates."""

    location: np.ndarray
    rotation_matrix: np.ndarray
    transform_matrix: np.ndarray


def sample_camera_pose(
    look_at_point: np.ndarray | list[float],
    min_distance: float = 0.5,
    max_distance: float = 2.0,
    min_elevation: float = 0.3,
    max_elevation: float = 0.9,
    azimuth: float | None = None,
    distance: float | None = None,
    elevation: float | None = None,
    inplane_rot: float = 0.0,
    target_image_pos: np.ndarray | list[float] | None = None,
    k_matrix: np.ndarray | list[list[float]] | None = None,
    rng: np.random.Generator | None = None,
) -> CameraPose:
    """Sample a single camera pose looking at a point.

    Args:
        look_at_point: The 3D point the camera should face.
        min_distance: Minimum distance from the point.
        max_distance: Maximum distance from the point.
        min_elevation: Minimum elevation [0, 1].
        max_elevation: Maximum elevation [0, 1].
        azimuth: Optional fixed azimuth (radians).
        distance: Optional fixed distance (meters).
        elevation: Optional fixed elevation [0, 1].
        inplane_rot: Optional roll rotation (radians).
        target_image_pos: Optional (u, v) pixel coordinates where the look_at_point should appear.
        k_matrix: Optional 3x3 intrinsic matrix (required if target_image_pos is set).
        rng: Optional NumPy random generator for isolation.

    Returns:
        A CameraPose object.
    """
    look_at_point = np.asarray(look_at_point)
    if rng is None:
        rng = np.random.default_rng()

    # 1. Sample spherical coordinates
    dist = distance if distance is not None else rng.uniform(min_distance, max_distance)
    elev = elevation if elevation is not None else rng.uniform(min_elevation, max_elevation)
    azim = azimuth if azimuth is not None else rng.uniform(0, 2 * np.pi)

    # 2. Convert elevation to spherical phi (angle from vertical Z)
    # elev=1 is directly above (phi=0), elev=0 is horizontal (phi=pi/2)
    phi = np.arccos(elev)

    # 3. Calculate 3D position relative to target
    dx = dist * np.sin(phi) * np.cos(azim)
    dy = dist * np.sin(phi) * np.sin(azim)
    dz = dist * np.cos(phi)

    location = look_at_point + np.array([dx, dy, dz])

    # 4. Compute rotation to look at target
    # Start with ideal upright rotation looking at center
    forward_vec = look_at_point - location
    rotation_matrix = look_at_rotation(forward_vec)

    # 5. Apply offset if target_image_pos is specified
    if target_image_pos is not None and k_matrix is not None:
        # Decompose K
        fx = k_matrix[0][0]
        fy = k_matrix[1][1]
        cx = k_matrix[0][2]
        cy = k_matrix[1][2]
        u, v = target_image_pos

        # Ray in OpenCV camera coordinates (Z forward)
        v_cv = np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
        # Ray in Blender camera coordinates (X right, Y up, Z backward => Forward is -Z)
        v_bl = np.array([v_cv[0], -v_cv[1], -v_cv[2]])
        v_bl_unit = v_bl / np.linalg.norm(v_bl)

        # We want to rotate the camera such that v_bl_unit points to forward_vec
        # ideal_R maps (0,0,-1) to forward_vec_unit
        # We want R such that R @ v_bl_unit = forward_vec_unit
        # Let R_offset be the rotation from (0,0,-1) to v_bl_unit
        # Then ideal_R = R @ R_offset  =>  R = ideal_R @ R_offset.T
        r_offset = rotation_matrix_from_vectors(np.array([0, 0, -1]), v_bl_unit)
        rotation_matrix = rotation_matrix @ r_offset.T

    # 6. Apply inplane rotation (roll) if specified
    if abs(inplane_rot) > 1e-6:
        # Rodrigues' rotation formula around the local Z axis
        # Local Z axis is the 3rd column of the rotation matrix
        k = rotation_matrix[:, 2]
        theta = inplane_rot

        K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])

        R_roll = np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * np.dot(K, K)
        rotation_matrix = np.dot(R_roll, rotation_matrix)

    transform_matrix = make_transformation_matrix(location, rotation_matrix)

    return CameraPose(
        location=location,
        rotation_matrix=rotation_matrix,
        transform_matrix=transform_matrix,
    )


def validate_camera_pose(
    pose: CameraPose,
    look_at_point: np.ndarray | list[float],
    min_distance: float = 0.4,
    min_height: float = 0.05,
) -> bool:
    """Validate that a camera pose is physically plausible.

    Args:
        pose: The camera pose to validate.
        look_at_point: The target point.
        min_distance: Minimum allowed distance to target.
        min_height: Minimum allowed height (Z) above 'floor' (Z=0).

    Returns:
        True if the pose is valid.
    """
    look_at_point = np.asarray(look_at_point)

    # Check distance
    dist = np.linalg.norm(pose.location - look_at_point)
    if dist < min_distance:
        return False

    # Check height
    # Check height
    return not pose.location[2] < min_height
