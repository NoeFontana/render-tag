from unittest.mock import MagicMock, patch

from render_tag.backend.bridge import bridge
from render_tag.backend.engine import RenderFacade
from render_tag.core.schema.renderer import RendererConfig


def test_render_facade_cv_safe_settings():
    """Verify that RenderFacade applies CV-Safe sampling and denoising settings."""
    # Ensure bridge is stabilized with mocks
    bridge.stabilize()

    # Create a mock for bridge.bproc.renderer
    mock_renderer = MagicMock()
    bridge.bproc.renderer = mock_renderer

    # Setup CV-Safe config
    cv_safe_config = RendererConfig(
        noise_threshold=0.02, max_samples=64, enable_denoising=True, denoiser_type="INTEL"
    )

    # We need to pass this config to RenderFacade somehow.
    # Currently RenderFacade __init__ only takes renderer_mode string.
    # We might need to update RenderFacade to take RendererConfig or
    # update how it's initialized in execute_recipe.

    # For TDD, let's assume we update RenderFacade to accept an optional config.
    RenderFacade(renderer_mode="cycles", config=cv_safe_config)

    # Verify BlenderProc renderer calls
    mock_renderer.set_noise_threshold.assert_called_once_with(0.02)
    mock_renderer.set_max_amount_of_samples.assert_called_once_with(64)
    mock_renderer.set_denoiser.assert_called_once_with("INTEL")
    mock_renderer.enable_diffuse_color_output.assert_called_once()
    mock_renderer.enable_normals_output.assert_called_once()


def test_execute_recipe_passes_config():
    """Verify that execute_recipe passes RendererConfig to RenderFacade."""
    from pathlib import Path

    from render_tag.backend.engine import RenderContext, execute_recipe
    from render_tag.data_io.writers import COCOWriter, CSVWriter, RichTruthWriter, SidecarWriter

    bridge.stabilize()
    mock_renderer = MagicMock()
    bridge.bproc.renderer = mock_renderer

    recipe = {
        "scene_id": 1,
        "renderer": {
            "noise_threshold": 0.03,
            "max_samples": 32,
            "enable_denoising": True,
            "denoiser_type": "INTEL",
        },
        "world": {},
        "objects": [],
        "cameras": [],
    }

    ctx = RenderContext(
        output_dir=Path("/tmp"),
        renderer_mode="cycles",
        csv_writer=MagicMock(spec=CSVWriter),
        coco_writer=MagicMock(spec=COCOWriter),
        rich_writer=MagicMock(spec=RichTruthWriter),
        sidecar_writer=MagicMock(spec=SidecarWriter),
        global_seed=42,
    )

    # We expect RenderFacade to be initialized with the config from recipe
    # and then _configure_engine to call bproc.renderer methods.

    # Mock some dependencies called in execute_recipe
    with patch("render_tag.backend.engine.RenderFacade", wraps=RenderFacade) as MockFacade:
        import contextlib

        with contextlib.suppress(Exception):
            execute_recipe(recipe, ctx)

        # Check if RenderFacade was called with the correct config
        _args, kwargs = MockFacade.call_args
        assert kwargs["config"].noise_threshold == 0.03
        assert kwargs["config"].max_samples == 32

    # Verify bproc calls happened
    mock_renderer.set_noise_threshold.assert_called_with(0.03)
    mock_renderer.set_max_amount_of_samples.assert_called_with(32)
