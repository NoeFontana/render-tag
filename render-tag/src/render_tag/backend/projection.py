"""
Projection utilities for render-tag.

This module handles projecting 3D tag corners to 2D image coordinates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from render_tag.backend.bridge import bproc, bpy, np

if TYPE_CHECKING:
    pass

from render_tag.geometry.visibility import (
    is_facing_camera,
    project_points,
    validate_visibility_metrics,
)


def project_corners_to_image(
    tag_obj: Any,
    camera_matrix: np.ndarray | None = None,
) -> list[tuple[float, float]] | None:
    """Project the 3D corners of a tag to 2D image coordinates.

    Args:
        tag_obj: The tag mesh object with corner_coords custom property
        camera_matrix: Optional camera matrix (uses current camera if None)

    Returns:
        List of 4 (x, y) tuples in image coordinates, or None if tag not visible
    """
    from render_tag.backend.assets import get_corner_world_coords

    # Get world coordinates of corners
    corners_world = get_corner_world_coords(tag_obj)

    if not corners_world or len(corners_world) != 4:
        return None

    # Project all corners at once using shared utility
    k_matrix = (
        camera_matrix if camera_matrix is not None else bproc.camera.get_intrinsics_as_K_matrix()
    )
    # Use current camera matrix instead of bproc stored poses
    # Blender matrix_world: right=X, up=Y, forward=-Z
    cam2world_blender = np.array(bpy.context.scene.camera.matrix_world)

    # Convert to OpenCV convention: right=X, down=-Y, forward=Z
    # We flip the Y and Z axes of the camera coordinate system
    flip_mat = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    cam2world = cam2world_blender @ flip_mat

    points_2d = project_points(np.array(corners_world), k_matrix, cam2world)

    if points_2d is None or len(points_2d) != 4:
        return None

    return [(float(p[0]), float(p[1])) for p in points_2d]


def check_tag_visibility(
    tag_obj: Any,
    min_visible_corners: int = 3,
) -> bool:
    """Check if a tag is visible in the current camera view."""
    corners_2d = project_corners_to_image(tag_obj)
    if corners_2d is None:
        return False

    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y

    is_visible, _ = validate_visibility_metrics(
        np.array(corners_2d), res_x, res_y, min_visible_corners=min_visible_corners
    )
    return is_visible


def check_tag_facing_camera(tag_obj: Any) -> bool:
    """Check if the tag's front face is facing the camera."""
    # Get the tag's normal vector in world space
    world_matrix = tag_obj.get_local2world_mat()
    local_normal = np.array([0, 0, 1, 0])
    world_normal = (world_matrix @ local_normal)[:3]

    tag_center = np.array(tag_obj.get_location())
    cam_pos = np.array(bpy.context.scene.camera.location)

    return is_facing_camera(tag_center, world_normal, cam_pos)


def compute_tag_area_in_image(corners_2d: list[tuple[float, float]]) -> float:
    """Compute the area of the tag in image space."""
    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y

    _, metrics = validate_visibility_metrics(np.array(corners_2d), res_x, res_y)
    return metrics["area"]


def compute_geometric_metadata(tag_obj: Any) -> dict[str, float]:
    """Compute geometric metadata for a tag.

    Returns:
        Dictionary with 'distance', 'angle_of_incidence', and 'pixel_area'.
    """
    # 1. Distance
    tag_location = np.array(tag_obj.get_location())
    cam_location = np.array(bpy.context.scene.camera.location)
    distance = float(np.linalg.norm(tag_location - cam_location))

    # 2. Angle of Incidence
    # Get tag normal in world space
    world_matrix = np.array(tag_obj.get_local2world_mat())
    local_normal = np.array([0, 0, 1, 0])
    world_normal = (world_matrix @ local_normal)[:3]
    world_normal /= np.linalg.norm(world_normal)

    # Vector from tag to camera
    to_cam = cam_location - tag_location
    to_cam /= np.linalg.norm(to_cam)

    # Cosine of angle is dot product
    cos_theta = np.clip(np.dot(world_normal, to_cam), -1.0, 1.0)
    angle_rad = np.arccos(cos_theta)
    angle_deg = float(np.degrees(angle_rad))

    # 3. Pixel Area
    corners_2d = project_corners_to_image(tag_obj)
    pixel_area = 0.0
    if corners_2d:
        pixel_area = compute_tag_area_in_image(corners_2d)

    return {
        "distance": distance,
        "angle_of_incidence": angle_deg,
        "pixel_area": pixel_area,
    }


def is_tag_sufficiently_visible(
    tag_obj: Any,
    min_area_pixels: int = 36,
    min_visible_corners: int = 4,
) -> bool:
    """Check if a tag is visible and large enough."""
    corners_2d = project_corners_to_image(tag_obj)
    if corners_2d is None:
        return False

    if not check_tag_facing_camera(tag_obj):
        return False

    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y

    is_visible, _ = validate_visibility_metrics(
        np.array(corners_2d),
        res_x,
        res_y,
        min_visible_corners=min_visible_corners,
        min_area_pixels=min_area_pixels,
    )
    return is_visible
