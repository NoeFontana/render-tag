"""
Visibility and projection geometry utilities for render-tag.

Handles facing checks and occupancy metrics without Blender dependencies.
"""

from __future__ import annotations

import numpy as np

from render_tag.geometry.math import compute_polygon_area


def is_facing_camera(
    tag_location: np.ndarray,
    tag_normal: np.ndarray,
    camera_location: np.ndarray,
    min_dot: float = 0.15,
) -> bool:
    """Check if a tag is facing the camera.

    Args:
        tag_location: 3D position of the tag center.
        tag_normal: 3D normal vector of the tag (world space).
        camera_location: 3D position of the camera.
        min_dot: Minimum dot product value (cos of angle).
                 0.15 corresponds to ~81 degrees.

    Returns:
        True if the tag faces the camera.
    """
    to_camera = camera_location - tag_location
    dist = np.linalg.norm(to_camera)
    if dist < 1e-6:
        return False

    to_camera_norm = to_camera / dist

    # Normalize tag normal if not already
    tag_normal_norm = tag_normal / np.linalg.norm(tag_normal)

    dot = np.dot(tag_normal_norm, to_camera_norm)
    return bool(dot > min_dot)


def project_points(
    points_3d: np.ndarray,
    k_matrix: np.ndarray,
    cam_to_world: np.ndarray,
) -> np.ndarray:
    """Project 3D world points to 2D image coordinates.

    Args:
        points_3d: (N, 3) world coordinates.
        k_matrix: (3, 3) intrinsic camera matrix.
        cam_to_world: (4, 4) camera-to-world transformation matrix.

    Returns:
        (N, 2) image coordinates (x, y).
    """
    # 1. Image of cam_to_world: world_to_cam
    world_to_cam = np.linalg.inv(cam_to_world)

    # 2. Convert to homogeneous coordinates
    points_hom = np.hstack([points_3d, np.ones((len(points_3d), 1))])

    # 3. Transform to camera space
    points_cam = (world_to_cam @ points_hom.T).T

    # 4. Project to 2D
    # Only keep points in front of camera (Z > 0)
    # Note: in many CV conventions Z is forward. In Blender camera space -Z is forward.
    # However, world_to_cam typically aligns so local Z is focal axis.
    # Let's check: points_cam[:, 2] is the depth.
    # If Blender convention: z < 0 is in front.
    # If standard CV: z > 0 is in front.
    # bproc world_to_cam usually ends up with Z forward in internal logic.

    # We'll project and check depth
    coords_2d = (k_matrix @ points_cam[:, :3].T).T

    # Avoid division by zero
    depth = coords_2d[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        coords_2d[:, 0] /= depth
        coords_2d[:, 1] /= depth

    return coords_2d[:, :2]


def validate_visibility_metrics(
    corners_2d: np.ndarray,
    image_width: int,
    image_height: int,
    min_visible_corners: int = 4,
    min_area_pixels: float = 0.0,
) -> tuple[bool, dict]:
    """Validate visibility metrics for a projected tag.

    Args:
        corners_2d: (4, 2) array of corner coordinates.
        image_width: Image width in pixels.
        image_height: Image height in pixels.
        min_visible_corners: Minimum corners that must be in-bounds.
        min_area_pixels: Minimum area in square pixels.

    Returns:
        (is_visible, metrics_dict)
    """
    # 1. Count corners in bounds
    in_bounds = (
        (corners_2d[:, 0] >= 0)
        & (corners_2d[:, 0] < image_width)
        & (corners_2d[:, 1] >= 0)
        & (corners_2d[:, 1] < image_height)
    )
    visible_corners = np.sum(in_bounds)

    # 2. Compute area
    area = compute_polygon_area(corners_2d)

    is_visible = bool((visible_corners >= min_visible_corners) and (area >= min_area_pixels))

    metrics = {
        "visible_corners": int(visible_corners),
        "area": float(area),
        "in_bounds_mask": in_bounds.tolist(),
    }

    return is_visible, metrics
