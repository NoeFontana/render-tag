
import pytest
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
    facade = RenderFacade(renderer_mode="cycles", config=config)
    
    # Verify BlenderProc renderer calls for light paths
    mock_renderer.set_light_bounces.assert_called_once_with(
        diffuse=2,
        glossy=4,
        transmission=1,
        transparency=6,
        volume=0  # Should be 0 by default for CV
    )
    mock_renderer.set_caustics.assert_called_once_with(reflective=True, refractive=True)
    assert bridge.bpy.context.scene.cycles.max_bounces == 5

def test_render_facade_light_path_defaults():
    """Verify that RenderFacade applies default CV-Safe light path settings."""
    bridge.stabilize()
    mock_renderer = MagicMock()
    bridge.bproc.renderer = mock_renderer
    
    config = RendererConfig() # Uses defaults
    facade = RenderFacade(renderer_mode="cycles", config=config)
    
    # Verify defaults are applied
    mock_renderer.set_light_bounces.assert_called_with(
        diffuse=2,
        glossy=4,
        transmission=0,
        transparency=4,
        volume=0
    )
    mock_renderer.set_caustics.assert_called_with(reflective=False, refractive=False)
    assert bridge.bpy.context.scene.cycles.max_bounces == 4
