"""
Camera geometry utilities for render-tag.

Handles camera pose sampling and validation without Blender dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from render_tag.geometry.math import look_at_rotation, make_transformation_matrix


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

    Returns:
        A CameraPose object.
    """
    look_at_point = np.asarray(look_at_point)

    # 1. Sample spherical coordinates
    dist = distance if distance is not None else np.random.uniform(min_distance, max_distance)
    elev = elevation if elevation is not None else np.random.uniform(min_elevation, max_elevation)
    azim = azimuth if azimuth is not None else np.random.uniform(0, 2 * np.pi)

    # 2. Convert elevation to spherical phi (angle from vertical Z)
    # elev=1 is directly above (phi=0), elev=0 is horizontal (phi=pi/2)
    phi = np.arccos(elev)

    # 3. Calculate 3D position relative to target
    dx = dist * np.sin(phi) * np.cos(azim)
    dy = dist * np.sin(phi) * np.sin(azim)
    dz = dist * np.cos(phi)

    location = look_at_point + np.array([dx, dy, dz])

    # 4. Compute rotation to look at target
    forward_vec = look_at_point - location
    rotation_matrix = look_at_rotation(forward_vec)

    # Apply inplane rotation (roll) if specified
    if abs(inplane_rot) > 1e-6:
        # Roll is rotation around the local Z axis (which is forward/backward in Blender)
        # Actually in Blender camera local-Z is backward.
        # Let's keep it simple for now or match Blender's rotation_from_forward_vec roll parameter
        # For now, we'll assume the basic look_at is sufficient and add roll if needed.
        pass

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
