
import pytest
from pydantic import ValidationError

from render_tag.core.schema.renderer import RendererConfig


def test_renderer_config_new_fields():
    """Verify that RendererConfig accepts the new CV-Safe parameters."""
    config = RendererConfig(
        noise_threshold=0.01,
        max_samples=64,
        enable_denoising=True,
        denoiser_type="INTEL"
    )
    assert config.noise_threshold == 0.01
    assert config.max_samples == 64
    assert config.enable_denoising is True
    assert config.denoiser_type == "INTEL"

def test_renderer_config_defaults():
    """Verify default values for the new fields."""
    config = RendererConfig()
    assert config.noise_threshold == 0.05
    assert config.max_samples == 128
    assert config.enable_denoising is True
    assert config.denoiser_type == "INTEL"

def test_renderer_config_validation():
    """Verify basic validation for the new fields."""
    with pytest.raises(ValidationError):
        # noise_threshold must be positive
        RendererConfig(noise_threshold=-0.1)
    
    with pytest.raises(ValidationError):
        # max_samples must be positive
        RendererConfig(max_samples=0)

def test_renderer_config_light_paths_defaults():
    """Verify default values for light path parameters."""
    config = RendererConfig()
    assert config.total_bounces == 4
    assert config.diffuse_bounces == 2
    assert config.glossy_bounces == 4
    assert config.transmission_bounces == 0
    assert config.transparent_bounces == 4
    assert config.enable_caustics is False

def test_renderer_config_light_paths_overrides():
    """Verify that light path parameters can be overridden."""
    config = RendererConfig(
        total_bounces=8,
        diffuse_bounces=4,
        glossy_bounces=6,
        transmission_bounces=2,
        transparent_bounces=10,
        enable_caustics=True
    )
    assert config.total_bounces == 8
    assert config.diffuse_bounces == 4
    assert config.glossy_bounces == 6
    assert config.transmission_bounces == 2
    assert config.transparent_bounces == 10
    assert config.enable_caustics is True

def test_renderer_config_light_paths_validation():
    """Verify validation for light path parameters."""
    with pytest.raises(ValidationError):
        RendererConfig(total_bounces=-1)
    with pytest.raises(ValidationError):
        RendererConfig(diffuse_bounces=-1)
