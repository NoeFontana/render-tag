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
            K=k_matrix,
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
        
        cx = intrinsics.get("principal_point_x")
        if cx is None:
            cx = resolution[0] / 2.0
            
        cy = intrinsics.get("principal_point_y")
        if cy is None:
            cy = resolution[1] / 2.0
        
        # For Blender 4.2+, ensure K is a list of lists of floats for mathutils compatibility
        K_list = [
            [float(fx), 0.0, float(cx)],
            [0.0, float(fy), float(cy)],
            [0.0, 0.0, 1.0],
        ]
        
        bproc.camera.set_intrinsics_from_K_matrix(
            K=K_list,
            image_width=resolution[0],
            image_height=resolution[1],
        )


def sample_camera_poses(
    num_samples: int,
    look_at_point: list[float],
    min_distance: float = 0.5,
    max_distance: float = 2.0,
    min_elevation: float = 0.3,
    max_elevation: float = 0.9,
    sampling_mode: str = "random",
    sample_idx: int = 0,
    total_samples: int = 1,
) -> list[Any]:
    """Sample camera poses from a partial sphere looking at a point.
    
    Args:
        num_samples: Number of camera poses to sample
        look_at_point: The 3D point cameras should look at
        min_distance: Minimum distance from look_at_point
        max_distance: Maximum distance from look_at_point
        min_elevation: Minimum elevation (0=horizontal, 1=directly above)
        max_elevation: Maximum elevation
        sampling_mode: "random", "distance", or "angle"
        sample_idx: Current sample index (for distance/angle modes)
        total_samples: Total number of samples in the sequence
        
    Returns:
        List of 4x4 camera-to-world transformation matrices
    """
    poses = []
    attempts = 0
    max_attempts = num_samples * 50 # Increase attempts
    
    # Pre-calculate steps for structured sampling if num_samples > 1
    # If num_samples is 1 (called in a loop), use sample_idx/total_samples
    if num_samples > 1:
        dist_steps = np.linspace(min_distance, max_distance, num_samples)
        elev_steps = np.linspace(min_elevation, max_elevation, num_samples)
    else:
        # Avoid division by zero if total_samples is 1
        t = sample_idx / (total_samples - 1) if total_samples > 1 else 0.5
        dist_steps = [min_distance + t * (max_distance - min_distance)]
        elev_steps = [min_elevation + t * (max_elevation - min_elevation)]
    
    while len(poses) < num_samples and attempts < max_attempts:
        i = len(poses)
        
        # Determine sampling parameters based on mode
        if sampling_mode == "distance":
            curr_dist = dist_steps[i]
            curr_elevation = np.random.uniform(min_elevation, max_elevation)
        elif sampling_mode == "angle":
            curr_dist = np.random.uniform(min_distance, max_distance)
            curr_elevation = elev_steps[i]
        else: # random
            curr_dist = np.random.uniform(min_distance, max_distance)
            curr_elevation = np.random.uniform(min_elevation, max_elevation)
            
        attempts += 1
        
        # Sample position
        azimuth = np.random.uniform(0, 2 * np.pi)
        
        # curr_elevation is normalized elevation [0, 1] where 1 is vertical.
        # Angle from vertical (phi) is acos(curr_elevation).
        phi = np.arccos(curr_elevation) 
        
        x = curr_dist * np.sin(phi) * np.cos(azimuth) + look_at_point[0]
        y = curr_dist * np.sin(phi) * np.sin(azimuth) + look_at_point[1]
        z = curr_dist * np.cos(phi) + look_at_point[2]
        
        location = np.array([x, y, z])
        
        # Check if location is valid
        if location[2] < 0.02: # Extremely low floor check
            continue
        
        # Compute rotation to look at the target
        rotation_matrix = bproc.camera.rotation_from_forward_vec(
            np.array(look_at_point) - location,
            inplane_rot=np.random.uniform(-0.1, 0.1),  # Small random roll
        )
        
        # Build the camera-to-world matrix
        cam2world = bproc.math.build_transformation_mat(location, rotation_matrix)
        
        # Validate the pose
        if is_valid_camera_pose(cam2world, look_at_point, min_distance):
            poses.append(cam2world)
    
    if len(poses) < num_samples:
        # Silent failure if called in loop, blender_main handles with its own attempts
        pass
    
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
