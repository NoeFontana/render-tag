"""
Camera utilities for render-tag.

This module handles camera pose sampling and intrinsics configuration.
"""

from __future__ import annotations

import math
from typing import Any

from render_tag.backend.bridge import bridge
from render_tag.core.logging import get_logger
from render_tag.generation.camera import (
    sample_camera_pose,
    validate_camera_pose,
)

logger = get_logger(__name__)


def set_camera_intrinsics(camera_config: dict) -> None:
    """Set camera intrinsics from configuration.

    Args:
        camera_config: Camera configuration dictionary (CameraRecipe format)
    """
    from render_tag.generation.intrinsics import resolve_intrinsics

    # Staff Engineer: Decouple calculation from application
    params = resolve_intrinsics(camera_config)
    res = params["resolution"]

    logger.info(f"Setting camera resolution to {res}, focal_length={params['fx']:.2f}")

    # Set resolution
    bridge.bproc.camera.set_resolution(res[0], res[1])

    # Apply computed K matrix
    bridge.bproc.camera.set_intrinsics_from_K_matrix(
        K=params["k_matrix"],
        image_width=res[0],
        image_height=res[1],
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
) -> list[bridge.np.ndarray]:
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
        dist_steps = bridge.np.linspace(min_distance, max_distance, num_samples)
        elev_steps = bridge.np.linspace(min_elevation, max_elevation, num_samples)
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


def add_camera_poses_to_scene(poses: list[bridge.np.ndarray]) -> None:
    """Add multiple camera poses to the BlenderProc scene.

    Args:
        poses: List of 4x4 camera-to-world matrices
    """
    for pose in poses:
        bridge.bproc.camera.add_camera_pose(pose)


def get_camera_k_matrix() -> bridge.np.ndarray:
    """Get the current camera's intrinsic matrix.

    Returns:
        3x3 camera intrinsic matrix K
    """
    return bridge.bproc.camera.get_intrinsics_as_K_matrix()


def setup_sensor_dynamics(
    pose_matrix: bridge.np.ndarray | list[list[float]],
    dynamics_recipe: dict[str, Any] | None,
) -> None:
    """Setup motion blur and rolling shutter artifacts.

    Args:
        pose_matrix: 4x4 camera-to-world transformation matrix at t=0
        dynamics_recipe: Dictionary containing velocity, shutter_time_ms,
                        and rolling_shutter_duration_ms.
    """
    if not dynamics_recipe:
        return

    velocity = dynamics_recipe.get("velocity")
    shutter_time_ms = dynamics_recipe.get("shutter_time_ms", 0.0)
    rolling_shutter_ms = dynamics_recipe.get("rolling_shutter_duration_ms", 0.0)

    # 1. Handle Motion Blur (Keyframing)
    if velocity and shutter_time_ms > 0:
        vx, vy, vz = velocity
        dt = shutter_time_ms / 1000.0

        # Ensure pose_matrix is suitable for mathutils
        start_matrix = bridge.mathutils.Matrix(pose_matrix)

        # Calculate end location: start_loc + velocity * dt
        end_loc = start_matrix.to_translation() + bridge.mathutils.Vector(
            (vx * dt, vy * dt, vz * dt)
        )

        end_matrix = start_matrix.copy()
        end_matrix.translation = end_loc

        # Frame 0 is the start pose, Frame 1 is the end pose
        bridge.bproc.camera.add_camera_pose(end_matrix, frame=1)
        bridge.bpy.context.scene.render.use_motion_blur = True
        bridge.bpy.context.scene.render.motion_blur_shutter = 1.0
    else:
        bridge.bpy.context.scene.render.use_motion_blur = False
    # 2. Handle Rolling Shutter (Cycles only)
    if rolling_shutter_ms > 0:
        engine = bridge.bpy.context.scene.render.engine
        if engine == "CYCLES":
            bridge.bpy.context.scene.render.rolling_shutter_type = "TOP_BOTTOM"

            # Map ms to Blender's 'duration' factor (0.0 to 1.0)
            if shutter_time_ms > 0:
                duration = min(1.0, rolling_shutter_ms / shutter_time_ms)
                bridge.bpy.context.scene.render.rolling_shutter_duration = duration
            else:
                bridge.bpy.context.scene.render.rolling_shutter_duration = 0.1
        else:
            logger.warning(
                f"Rolling shutter simulation requested for {engine}, but it is only "
                "supported natively in CYCLES. Effect will be ignored."
            )


def setup_motion_blur(
    pose_matrix: bridge.np.ndarray | list[list[float]],
    velocity: list[float] | None,
    shutter_time_ms: float,
) -> None:
    """Legacy stub for motion blur setup.

    Deprecated: Use setup_sensor_dynamics instead.
    """
    dynamics = {
        "velocity": velocity,
        "shutter_time_ms": shutter_time_ms,
        "rolling_shutter_duration_ms": 0.0,
    }
    setup_sensor_dynamics(pose_matrix, dynamics)
