
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
