"""
Projection utilities for render-tag.

This module handles projecting 3D tag corners to 2D image coordinates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import numpy as np

# BlenderProc imports (only available inside Blender)
try:
    import blenderproc as bproc
    import bpy
    import numpy as np
except ImportError:
    bproc = None  # type: ignore
    bpy = None  # type: ignore
    np = None  # type: ignore


# Import pure-Python geometry modules
try:
    import os
    import sys
    from pathlib import Path
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(os.path.dirname(scripts_dir))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        
    from render_tag.geometry.visibility import (
        is_facing_camera,
        project_points,
        validate_visibility_metrics,
    )
    GEOMETRY_AVAILABLE = True
except ImportError:
    GEOMETRY_AVAILABLE = False


def project_corners_to_image(
    tag_obj: Any,
    camera_matrix: Optional[np.ndarray] = None,
) -> Optional[list[tuple[float, float]]]:
    """Project the 3D corners of a tag to 2D image coordinates.
    
    Args:
        tag_obj: The tag mesh object with corner_coords custom property
        camera_matrix: Optional camera matrix (uses current camera if None)
        
    Returns:
        List of 4 (x, y) tuples in image coordinates, or None if tag not visible
    """
    from render_tag.scripts.assets import get_corner_world_coords
    
    # Get world coordinates of corners
    corners_world = get_corner_world_coords(tag_obj)
    
    if not corners_world or len(corners_world) != 4:
        return None
    
    # Project all corners at once using shared utility
    k_matrix = camera_matrix if camera_matrix is not None else bproc.camera.get_intrinsics_as_K_matrix()
    cam2world = bproc.camera.get_camera_pose(bpy.context.scene.frame_current)
    
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
        np.array(corners_2d), 
        res_x, 
        res_y, 
        min_visible_corners=min_visible_corners
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
        min_area_pixels=min_area_pixels
    )
    return is_visible

