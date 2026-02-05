"""
Camera utilities for render-tag.

This module handles camera pose sampling and intrinsics configuration.
"""

from __future__ import annotations

import math
import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import numpy as np

# BlenderProc imports (only available inside Blender)
try:
    import blenderproc as bproc
    import bpy
    import mathutils
    import numpy as np
except ImportError:
    bproc = None  # type: ignore
    bpy = None  # type: ignore
    mathutils = None  # type: ignore
    np = None  # type: ignore

from render_tag.geometry.camera import (
    sample_camera_pose,
    validate_camera_pose,
)


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
    elevation: float | None = None,
    azimuth: float | None = None,
) -> list[np.ndarray]:
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
    max_attempts = num_samples * 50

    # Pre-calculate steps for structured sampling if num_samples > 1
    if num_samples > 1:
        dist_steps = np.linspace(min_distance, max_distance, num_samples)
        elev_steps = np.linspace(min_elevation, max_elevation, num_samples)
    else:
        t = sample_idx / (total_samples - 1) if total_samples > 1 else 0.5
        dist_steps = [min_distance + t * (max_distance - min_distance)]
        elev_steps = [min_elevation + t * (max_elevation - min_elevation)]

    while len(poses) < num_samples and attempts < max_attempts:
        i = len(poses)
        attempts += 1

        # Determine sampling parameters based on mode
        curr_dist = None
        curr_elev = None

        if sampling_mode == "distance":
            curr_dist = dist_steps[i]
        elif sampling_mode == "angle":
            curr_elev = elev_steps[i]

        # 1. Use pure-Python geometry for sampling
        pose = sample_camera_pose(
            look_at_point=look_at_point,
            min_distance=min_distance,
            max_distance=max_distance,
            min_elevation=min_elevation,
            max_elevation=max_elevation,
            distance=curr_dist,
            elevation=curr_elev if curr_elev is not None else elevation,
            azimuth=azimuth,
        )

        # 2. Use pure-Python geometry for validation
        if validate_camera_pose(pose, look_at_point, min_distance):
            poses.append(pose.transform_matrix)

    return poses


def add_camera_poses_to_scene(poses: list[np.ndarray]) -> None:
    """Add multiple camera poses to the BlenderProc scene.

    Args:
        poses: List of 4x4 camera-to-world matrices
    """
    for pose in poses:
        bproc.camera.add_camera_pose(pose)


def get_camera_k_matrix() -> np.ndarray:
    """Get the current camera's intrinsic matrix.

    Returns:
        3x3 camera intrinsic matrix K
    """
    return bproc.camera.get_intrinsics_as_K_matrix()


def setup_sensor_dynamics(


    pose_matrix: np.ndarray | list[list[float]],


    dynamics_recipe: dict[str, Any] | None,


) -> None:


    """Setup motion blur and rolling shutter artifacts.





    Args:


        pose_matrix: 4x4 camera-to-world transformation matrix at t=0


        dynamics_recipe: Dictionary containing velocity, shutter_time_ms, 


                        and rolling_shutter_duration_ms.


    """


    if not dynamics_recipe or not bpy:


        return





    velocity = dynamics_recipe.get("velocity")


    shutter_time_ms = dynamics_recipe.get("shutter_time_ms", 0.0)


    rolling_shutter_ms = dynamics_recipe.get("rolling_shutter_duration_ms", 0.0)





    # 1. Handle Motion Blur (Keyframing)


    if velocity and shutter_time_ms > 0 and bproc and mathutils:


        vx, vy, vz = velocity


        dt = shutter_time_ms / 1000.0





        # Ensure pose_matrix is suitable for mathutils


        start_matrix = mathutils.Matrix(pose_matrix)





        # Calculate end location: start_loc + velocity * dt


        end_loc = start_matrix.to_translation() + mathutils.Vector((vx * dt, vy * dt, vz * dt))





        end_matrix = start_matrix.copy()


        end_matrix.translation = end_loc





        # Frame 0 is the start pose, Frame 1 is the end pose


        bproc.camera.add_camera_pose(end_matrix, frame=1)


        bpy.context.scene.render.use_motion_blur = True


        bpy.context.scene.render.motion_blur_shutter = 1.0


    else:


        bpy.context.scene.render.use_motion_blur = False





    # 2. Handle Rolling Shutter (Cycles only)


    if rolling_shutter_ms > 0:


        engine = bpy.context.scene.render.engine


        if engine == "CYCLES":


            bpy.context.scene.render.rolling_shutter_type = "TOP_BOTTOM"


            


            # Map ms to Blender's 'duration' factor (0.0 to 1.0)


            # In our pipeline, we assume 1.0 corresponds to the entire exposure 


            # (which we defined as 1 frame duration in the motion blur setup above).


            # So duration = rolling_shutter_ms / shutter_time_ms


            if shutter_time_ms > 0:


                duration = min(1.0, rolling_shutter_ms / shutter_time_ms)


                bpy.context.scene.render.rolling_shutter_duration = duration


            else:


                # Fallback if shutter time is 0 but rolling shutter is set


                bpy.context.scene.render.rolling_shutter_duration = 0.1


        else:


            logger.warning(


                f"Rolling shutter simulation requested for {engine}, but it is only "


                "supported natively in CYCLES. Effect will be ignored."


            )

