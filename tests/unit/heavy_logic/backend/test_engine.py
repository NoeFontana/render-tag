from unittest.mock import MagicMock

import pytest

from render_tag.backend.bridge import bridge
from render_tag.backend.engine import RenderFacade
from render_tag.core.schema.renderer import RendererConfig


@pytest.mark.parametrize(
    "config_params, expected_bounces, expected_caustics",
    [
        (
            {
                "total_bounces": 5,
                "diffuse_bounces": 2,
                "glossy_bounces": 4,
                "transmission_bounces": 1,
                "transparent_bounces": 6,
                "enable_caustics": True,
            },
            {
                "diffuse_bounces": 2,
                "glossy_bounces": 4,
                "transmission_bounces": 1,
                "transparent_max_bounces": 6,
                "volume_bounces": 0,
                "max_bounces": 5,
            },
            True,
        ),
        (
            {},  # Defaults
            {
                "diffuse_bounces": 2,
                "glossy_bounces": 4,
                "transmission_bounces": 0,
                "transparent_max_bounces": 4,
                "volume_bounces": 0,
                "max_bounces": 4,
            },
            False,
        ),
    ],
)
def test_render_facade_light_path_settings(config_params, expected_bounces, expected_caustics):
    """Verify that RenderFacade applies CV-Safe light path settings (parameterized)."""
    mock_renderer = MagicMock()
    bridge.bproc.renderer = mock_renderer
    
    config = RendererConfig(**config_params)
    RenderFacade(renderer_mode="cycles", config=config)
    
    mock_renderer.set_light_bounces.assert_called_with(**expected_bounces)
    assert bridge.bpy.context.scene.cycles.caustics_reflective is expected_caustics
    assert bridge.bpy.context.scene.cycles.caustics_refractive is expected_caustics
