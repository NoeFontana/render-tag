from unittest.mock import MagicMock, patch

from render_tag.backend.engine import _render_camera_and_save


@patch("render_tag.backend.engine.bridge")
def test_render_camera_subframe_synchronization(mock_bridge):
    """
    Test that frame_set(subframe=0.5) is called BEFORE renderer.render_camera.
    """
    import numpy as np

    mock_bridge.np = np

    renderer = MagicMock()
    # Record when subframe is set vs when render is called
    execution_order = []

    def mock_frame_set(frame, subframe=0.0):
        execution_order.append(f"frame_set_{subframe}")

    def mock_render(recipe):
        execution_order.append("render_called")
        return {"img": []}

    mock_bridge.bpy.context.scene.frame_set.side_effect = mock_frame_set
    renderer.render_camera.side_effect = mock_render

    ctx = MagicMock()
    ctx.output_dir = MagicMock()
    provenance = {}
    res = [640, 480]
    cam_recipe = MagicMock()
    recipe = MagicMock()
    recipe.scene_id = 0
    scene_logger = MagicMock()

    # ACT
    _render_camera_and_save(renderer, 0, cam_recipe, recipe, ctx, scene_logger, provenance, res)

    # VERIFY
    # Current behavior: ['render_called', 'frame_set_0.5']
    # Desired behavior: ['frame_set_0.5', 'render_called']
    assert "frame_set_0.5" in execution_order
    assert "render_called" in execution_order

    idx_frame = execution_order.index("frame_set_0.5")
    idx_render = execution_order.index("render_called")

    # THIS SHOULD FAIL with current code
    assert idx_frame < idx_render, f"frame_set was called after render! Order: {execution_order}"
