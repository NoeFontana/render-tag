from unittest.mock import MagicMock, patch

import numpy as np

# We get setup_sensor_dynamics knowing it uses bridge internally
with (
    patch("render_tag.backend.bridge.bridge.bpy", create=True) as mock_bpy,
    patch("render_tag.backend.bridge.bridge.bproc", create=True) as mock_bproc,
):
    from render_tag.backend.camera import setup_sensor_dynamics


def test_setup_sensor_dynamics_rolling_shutter():
    """Verify that rolling shutter duration is correctly set in Blender context."""
    mock_bpy = MagicMock()
    mock_bpy.context.scene.render.engine = "CYCLES"  # Must be CYCLES for rolling shutter
    mock_bproc = MagicMock()

    pose_matrix = np.eye(4)
    dynamics_recipe = {
        "velocity": [1.0, 0.0, 0.0],
        "shutter_time_ms": 10.0,
        "rolling_shutter_duration_ms": 5.0,
    }

    with (
        patch("render_tag.backend.bridge.bridge.bpy", mock_bpy),
        patch("render_tag.backend.bridge.bridge.bproc", mock_bproc),
        patch("render_tag.backend.bridge.bridge.mathutils", create=True),
    ):
        setup_sensor_dynamics(pose_matrix, dynamics_recipe)

        assert mock_bpy.context.scene.render.rolling_shutter_type == "TOP_BOTTOM"
        # 5.0 ms / 10.0 ms = 0.5
        assert mock_bpy.context.scene.render.rolling_shutter_duration == 0.5


def test_setup_sensor_dynamics_eevee_warning():
    """Verify that a warning is issued when using rolling shutter with Eevee."""
    mock_bpy = MagicMock()
    mock_bpy.context.scene.render.engine = "BLENDER_EEVEE"

    pose_matrix = np.eye(4)
    dynamics_recipe = {"rolling_shutter_duration_ms": 5.0}

    with (
        patch("render_tag.backend.bridge.bridge.bpy", mock_bpy),
        patch("render_tag.backend.camera.logger") as mock_logger,
        patch("render_tag.backend.bridge.bridge.mathutils", create=True),
    ):
        setup_sensor_dynamics(pose_matrix, dynamics_recipe)
        assert mock_logger.warning.called
        assert "Rolling shutter" in mock_logger.warning.call_args[0][0]
