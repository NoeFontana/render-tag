from unittest.mock import MagicMock

from render_tag.backend.bridge import bridge
from render_tag.backend.engine import RenderFacade
from render_tag.core.schema.renderer import RendererConfig


def test_render_facade_light_path_settings():
    """Verify that RenderFacade applies CV-Safe light path settings."""
    # Ensure bridge is stabilized with mocks
    bridge.stabilize()
    
    # Create a mock for bridge.bproc.renderer
    mock_renderer = MagicMock()
    bridge.bproc.renderer = mock_renderer
    
    # Setup CV-Safe config with light path parameters
    config = RendererConfig(
        total_bounces=5,
        diffuse_bounces=2,
        glossy_bounces=4,
        transmission_bounces=1,
        transparent_bounces=6,
        enable_caustics=True
    )
    
    # Initialize RenderFacade with the config
    RenderFacade(renderer_mode="cycles", config=config)
    
    # Verify BlenderProc renderer calls for light paths
    mock_renderer.set_light_bounces.assert_called_once_with(
        diffuse_bounces=2,
        glossy_bounces=4,
        transmission_bounces=1,
        transparent_max_bounces=6,
        volume_bounces=0,
        max_bounces=5
    )
    assert bridge.bpy.context.scene.cycles.caustics_reflective is True
    assert bridge.bpy.context.scene.cycles.caustics_refractive is True

def test_render_facade_light_path_defaults():
    """Verify that RenderFacade applies default CV-Safe light path settings."""
    bridge.stabilize()
    mock_renderer = MagicMock()
    bridge.bproc.renderer = mock_renderer
    
    config = RendererConfig() # Uses defaults
    RenderFacade(renderer_mode="cycles", config=config)
    
    # Verify defaults are applied
    mock_renderer.set_light_bounces.assert_called_with(
        diffuse_bounces=2,
        glossy_bounces=4,
        transmission_bounces=0,
        transparent_max_bounces=4,
        volume_bounces=0,
        max_bounces=4
    )
    assert bridge.bpy.context.scene.cycles.caustics_reflective is False
    assert bridge.bpy.context.scene.cycles.caustics_refractive is False
