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


def project_corners_to_image(
    tag_obj: Any,
    camera_matrix: Optional[Any] = None,
) -> Optional[list[tuple[float, float]]]:
    """Project the 3D corners of a tag to 2D image coordinates.
    
    Args:
        tag_obj: The tag mesh object with corner_coords custom property
        camera_matrix: Optional camera matrix (uses current camera if None)
        
    Returns:
        List of 4 (x, y) tuples in image coordinates, or None if tag not visible
    """
    from assets import get_corner_world_coords
    
    # Get world coordinates of corners
    corners_world = get_corner_world_coords(tag_obj)
    
    if not corners_world or len(corners_world) != 4:
        return None
    
    # Project all corners at once using BlenderProc's plural function
    points_2d = bproc.camera.project_points(np.array(corners_world))
    
    if points_2d is None or len(points_2d) != 4:
        return None
        
    corners_2d = [(float(p[0]), float(p[1])) for p in points_2d]
    
    # Validate that corners are within image bounds
    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y
    width, height = res_x, res_y
    
    for x, y in corners_2d:
        if x < 0 or x >= width or y < 0 or y >= height:
            # Corner is outside image bounds
            # We still return it but could filter here if needed
            pass
    
    return corners_2d


def check_tag_visibility(
    tag_obj,
    min_visible_corners: int = 3,
) -> bool:
    """Check if a tag is visible in the current camera view.
    
    Args:
        tag_obj: The tag mesh object
        min_visible_corners: Minimum number of corners that must be visible
        
    Returns:
        True if the tag is sufficiently visible
    """
    corners_2d = project_corners_to_image(tag_obj)
    
    if corners_2d is None:
        return False
    
    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y
    width, height = res_x, res_y
    
    visible_count = 0
    for x, y in corners_2d:
        if 0 <= x < width and 0 <= y < height:
            visible_count += 1
    
    return visible_count >= min_visible_corners


def check_tag_facing_camera(tag_obj) -> bool:
    """Check if the tag's front face is facing the camera.
    
    Args:
        tag_obj: The tag mesh object
        
    Returns:
        True if the tag is facing the camera (not flipped away)
    """
    # Get the tag's normal vector in world space
    # For a plane, the normal is typically the Z axis in local space
    local_normal = np.array([0, 0, 1, 0])
    
    world_matrix = tag_obj.get_local2world_mat()
    world_normal = world_matrix @ local_normal
    world_normal = world_normal[:3]
    world_normal = world_normal / np.linalg.norm(world_normal)
    
    # Get the vector from tag center to camera
    tag_center = tag_obj.get_location()
    cam_pose = bproc.camera.get_camera_pose()
    cam_pos = cam_pose[:3, 3]
    
    to_camera = cam_pos - np.array(tag_center)
    to_camera = to_camera / np.linalg.norm(to_camera)
    
    # Dot product: positive means facing camera
    dot = np.dot(world_normal, to_camera)
    
    return dot > 0


def compute_tag_area_in_image(corners_2d: list[tuple[float, float]]) -> float:
    """Compute the area of the tag in image space using the Shoelace formula.
    
    Args:
        corners_2d: List of 4 (x, y) corner coordinates
        
    Returns:
        Area in square pixels
    """
    if len(corners_2d) != 4:
        return 0.0
    
    # Shoelace formula for polygon area
    n = len(corners_2d)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += corners_2d[i][0] * corners_2d[j][1]
        area -= corners_2d[j][0] * corners_2d[i][1]
    
    return abs(area) / 2.0
