"""
Camera utilities for render-tag.

This module handles camera pose sampling and intrinsics configuration.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

# BlenderProc imports (only available inside Blender)
try:
    import blenderproc as bproc
    import numpy as np
except ImportError:
    bproc = None  # type: ignore
    np = None  # type: ignore


def set_camera_intrinsics(camera_config: dict) -> None:
    """Set camera intrinsics from configuration.
    
    Args:
        camera_config: Camera configuration dictionary containing resolution, fov, intrinsics
    """
    resolution = camera_config.get("resolution", [640, 480])
    fov = camera_config.get("fov", 60.0)
    
    # Set resolution
    bproc.camera.set_resolution(resolution[0], resolution[1])
    
    # Check for explicit intrinsics
    intrinsics = camera_config.get("intrinsics", {})
    k_matrix = intrinsics.get("k_matrix")
    
    if k_matrix:
        # Use explicit K matrix
        bproc.camera.set_intrinsics_from_K_matrix(
            K=np.array(k_matrix),
            image_width=resolution[0],
            image_height=resolution[1],
        )
    else:
        # Compute from FOV or other parameters
        focal_length = intrinsics.get("focal_length")
        focal_length_x = intrinsics.get("focal_length_x")
        focal_length_y = intrinsics.get("focal_length_y")
        
        if focal_length_x and focal_length_y:
            fx, fy = focal_length_x, focal_length_y
        elif focal_length:
            fx = fy = focal_length
        else:
            # Compute from FOV
            fx = fy = resolution[0] / (2.0 * math.tan(math.radians(fov / 2.0)))
        
        cx = intrinsics.get("principal_point_x", resolution[0] / 2.0)
        cy = intrinsics.get("principal_point_y", resolution[1] / 2.0)
        
        K = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1],
        ])
        
        bproc.camera.set_intrinsics_from_K_matrix(
            K=K,
            image_width=resolution[0],
            image_height=resolution[1],
        )


def sample_camera_poses(
    num_samples: int,
    look_at_point: list[float],
    min_distance: float = 0.5,
    max_distance: float = 2.0,
    min_elevation: float = 0.1,
    max_elevation: float = 0.8,
) -> list[Any]:
    """Sample camera poses from a partial sphere looking at a point.
    
    Args:
        num_samples: Number of camera poses to sample
        look_at_point: The 3D point cameras should look at
        min_distance: Minimum distance from look_at_point
        max_distance: Maximum distance from look_at_point
        min_elevation: Minimum elevation angle (0=horizontal, 1=directly above)
        max_elevation: Maximum elevation angle
        
    Returns:
        List of 4x4 camera-to-world transformation matrices
    """
    poses = []
    attempts = 0
    max_attempts = num_samples * 10
    
    while len(poses) < num_samples and attempts < max_attempts:
        attempts += 1
        
        # Sample a position on a partial sphere
        location = bproc.sampler.part_sphere(
            center=look_at_point,
            radius=np.random.uniform(min_distance, max_distance),
            mode="SURFACE",
            dist_above_center=min_elevation,
            dist_below_center=0,  # Don't go below the look_at_point
        )
        
        # Check if location is valid (above ground plane)
        if location[2] < 0.1:
            continue
        
        # Compute rotation to look at the target
        rotation_matrix = bproc.camera.rotation_from_forward_vec(
            np.array(look_at_point) - np.array(location),
            inplane_rot=np.random.uniform(-0.1, 0.1),  # Small random roll
        )
        
        # Build the camera-to-world matrix
        cam2world = bproc.math.build_transformation_mat(location, rotation_matrix)
        
        # Validate the pose
        if is_valid_camera_pose(cam2world, look_at_point, min_distance):
            poses.append(cam2world)
    
    if len(poses) < num_samples:
        print(f"Warning: Only sampled {len(poses)}/{num_samples} valid camera poses")
    
    return poses


def is_valid_camera_pose(
    cam2world: Any,
    look_at_point: list[float],
    min_distance: float,
) -> bool:
    """Validate a camera pose.
    
    Args:
        cam2world: 4x4 camera-to-world transformation matrix
        look_at_point: The point the camera should be looking at
        min_distance: Minimum allowed distance to the target
        
    Returns:
        True if the pose is valid
    """
    # Extract camera position
    cam_pos = cam2world[:3, 3]
    
    # Check distance to target
    distance = np.linalg.norm(cam_pos - np.array(look_at_point))
    if distance < min_distance:
        return False
    
    # Check if camera is above the floor
    if cam_pos[2] < 0.05:
        return False
    
    return True


def add_camera_poses_to_scene(poses: list[Any]) -> None:
    """Add multiple camera poses to the BlenderProc scene.
    
    Args:
        poses: List of 4x4 camera-to-world matrices
    """
    for pose in poses:
        bproc.camera.add_camera_pose(pose)


def get_camera_k_matrix() -> Any:
    """Get the current camera's intrinsic matrix.
    
    Returns:
        3x3 camera intrinsic matrix K
    """
    return bproc.camera.get_intrinsics_as_K_matrix()
