from __future__ import annotations

from unittest.mock import patch

import numpy as np

from render_tag.backend.engine import RenderFacade
from render_tag.core.schema import CameraIntrinsics, CameraRecipe


@patch("render_tag.backend.engine.bridge")
def test_render_camera_no_duplicate_pose(mock_bridge):
    """
    Test that render_camera calls add_camera_pose exactly once.
    """
    renderer = RenderFacade()

    # Mock camera recipe
    camera_recipe = CameraRecipe(
        transform_matrix=np.eye(4).tolist(),
        intrinsics=CameraIntrinsics(resolution=[640, 480], k_matrix=np.eye(3).tolist(), fov=60.0),
    )

    # Setup mocks for dependencies called within render_camera
    mock_bridge.np = np
    mock_bridge.bproc.renderer.render.return_value = {"colors": [np.zeros((480, 640, 3))]}

    # We need to mock setup_sensor_dynamics and set_camera_intrinsics
    # because they might have complex side effects or further imports.
    with (
        patch("render_tag.backend.camera.setup_sensor_dynamics"),
        patch("render_tag.backend.camera.set_camera_intrinsics"),
    ):
        renderer.render_camera(camera_recipe)

        # VERIFY
        # add_camera_pose should be called exactly ONCE (currently it will be TWICE)
        mock_bridge.bproc.camera.add_camera_pose.assert_called_once()
