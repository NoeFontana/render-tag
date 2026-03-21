"""
Camera utilities for render-tag.

This module handles camera intrinsics and sensor dynamics configuration.
"""

from __future__ import annotations

from render_tag.backend.bridge import bridge
from render_tag.core.logging import get_logger
from render_tag.core.schema import CameraRecipe, SensorDynamicsRecipe

logger = get_logger(__name__)


def set_camera_intrinsics(camera_recipe: CameraRecipe) -> None:
    """Set camera intrinsics from configuration.

    Args:
        camera_recipe: Camera recipe (CameraRecipe format)
    """
    intrinsics = camera_recipe.intrinsics
    res = intrinsics.resolution
    k_matrix = intrinsics.k_matrix

    if not k_matrix:
        # Emergency fallback for legacy or minimal test recipes
        import math

        fov = camera_recipe.fov or 60.0
        fx = fy = res[0] / (2.0 * math.tan(math.radians(fov / 2.0)))
        cx, cy = res[0] / 2.0, res[1] / 2.0
        k_matrix = [[float(fx), 0.0, float(cx)], [0.0, float(fy), float(cy)], [0.0, 0.0, 1.0]]
        logger.warning(f"No k_matrix found in recipe. Using fallback FOV={fov}")

    logger.info(f"Setting camera resolution to {res}")

    # Set resolution
    bridge.bproc.camera.set_resolution(res[0], res[1])

    # Staff Engineer: BlenderProc's `set_intrinsics_from_K_matrix` hardcodes a sensor shift
    # calculation based on `cx - (image_width - 1) / 2`. Because our strictly continuous
    # OpenCV K matrix uses `cx = image_width / 2.0`, BlenderProc incorrectly shifts the physical
    # sensor by 0.5 pixels. To prevent this and keep the Blender camera perfectly centered
    # (which perfectly matches our pure Python OpenCV projection math), we subtract 0.5 here.
    import copy

    bproc_k_matrix = copy.deepcopy(k_matrix)
    bproc_k_matrix[0][2] -= 0.5  # cx
    bproc_k_matrix[1][2] -= 0.5  # cy

    # Apply pre-calculated K matrix
    bridge.bproc.camera.set_intrinsics_from_K_matrix(
        K=bproc_k_matrix,
        image_width=res[0],
        image_height=res[1],
    )


def setup_sensor_dynamics(
    pose_matrix: bridge.np.ndarray | list[list[float]],
    dynamics_recipe: SensorDynamicsRecipe | None,
) -> None:
    """Setup motion blur and rolling shutter artifacts.

    Args:
        pose_matrix: 4x4 camera-to-world transformation matrix at t=0
        dynamics_recipe: Recipe containing velocity, shutter_time_ms,
                        and rolling_shutter_duration_ms.
    """
    if not dynamics_recipe:
        return

    velocity = dynamics_recipe.velocity
    shutter_time_ms = dynamics_recipe.shutter_time_ms or 0.0
    rolling_shutter_ms = dynamics_recipe.rolling_shutter_duration_ms or 0.0

    # 1. Handle Motion Blur (Keyframing)
    if velocity and shutter_time_ms > 0:
        vx, vy, vz = velocity
        dt = shutter_time_ms / 1000.0

        # Ensure pose_matrix is suitable for mathutils
        start_matrix = bridge.mathutils.Matrix(pose_matrix)

        # Calculate end location: start_loc + velocity * dt
        end_loc = start_matrix.to_translation() + bridge.mathutils.Vector(
            (vx * dt, vy * dt, vz * dt)
        )  # type: ignore

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
