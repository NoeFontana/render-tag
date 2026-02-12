"""
Projection utilities for render-tag.

This module handles projecting 3D tag corners to 2D image coordinates.
Now uses pure-Python geometry math for core calculations.
"""

from __future__ import annotations

from typing import Any

from render_tag.backend.bridge import bproc, bpy, np
from render_tag.geometry.projection_math import (
    calculate_angle_of_incidence,
    calculate_distance,
    get_opencv_camera_matrix,
    get_world_normal,
    calculate_relative_pose,
)
from render_tag.geometry.visibility import (
    is_facing_camera,
    project_points,
    validate_visibility_metrics,
)


def project_corners_to_image(
    tag_obj: Any,
    camera_matrix: np.ndarray | None = None,
) -> list[tuple[float, float]] | None:
    """Project the 3D corners of a tag to 2D image coordinates."""
    from render_tag.backend.assets import get_corner_world_coords

    corners_world = get_corner_world_coords(tag_obj)
    if not corners_world or len(corners_world) != 4:
        return None

    k_matrix = (
        camera_matrix if camera_matrix is not None else bproc.camera.get_intrinsics_as_K_matrix()
    )

    # Use bridge/math logic for matrix conversion
    blender_cam_mat = np.array(bpy.context.scene.camera.matrix_world)
    cam2world = get_opencv_camera_matrix(blender_cam_mat)

    points_2d = project_points(np.array(corners_world), k_matrix, cam2world)
    if points_2d is None or len(points_2d) != 4:
        return None

    return [(float(p[0]), float(p[1])) for p in points_2d]


def check_tag_visibility(tag_obj: Any, min_visible_corners: int = 3) -> bool:
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
    world_matrix = np.array(tag_obj.get_local2world_mat())
    world_normal = get_world_normal(world_matrix)

    tag_center = np.array(tag_obj.get_location())
    cam_pos = np.array(bpy.context.scene.camera.location)

    return is_facing_camera(tag_center, world_normal, cam_pos)


def compute_tag_area_in_image(corners_2d: list[tuple[float, float]]) -> float:
    """Compute the area of the tag in image space."""
    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y

    _, metrics = validate_visibility_metrics(np.array(corners_2d), res_x, res_y)
    return metrics["area"]


def compute_geometric_metadata(tag_obj: Any) -> dict[str, Any]:
    """Compute geometric metadata for a tag."""
    tag_location = np.array(tag_obj.get_location())
    cam_location = np.array(bpy.context.scene.camera.location)
    world_matrix = np.array(tag_obj.get_local2world_mat())
    blender_cam_mat = np.array(bpy.context.scene.camera.matrix_world)

    # Use pure math layer
    distance = calculate_distance(tag_location, cam_location)

    world_normal = get_world_normal(world_matrix)
    angle_deg = calculate_angle_of_incidence(tag_location, world_normal, cam_location)

    corners_2d = project_corners_to_image(tag_obj)
    pixel_area = compute_tag_area_in_image(corners_2d) if corners_2d else 0.0

    # High-Precision Pose
    pose = calculate_relative_pose(world_matrix, blender_cam_mat)

    return {
        "distance": distance,
        "angle_of_incidence": angle_deg,
        "pixel_area": pixel_area,
        "position": pose["position"],
        "rotation_quaternion": pose["rotation_quaternion"],
    }


def get_valid_detections(tag_objects: list[Any]) -> list[tuple[Any, list[tuple[float, float]]]]:
    """
    Filter visible tags and return their projected corners.

    Args:
        tag_objects: List of tag objects (BlenderProc wrappers or similar).

    Returns:
        List of (tag_obj, corners_2d) tuples for visible tags.
    """
    valid_detections = []

    for tag_obj in tag_objects:
        corners_2d = project_corners_to_image(tag_obj)

        if corners_2d is not None and check_tag_visibility(tag_obj):
            valid_detections.append((tag_obj, corners_2d))

    return valid_detections
