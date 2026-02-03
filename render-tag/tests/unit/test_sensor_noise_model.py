import pytest
from pydantic import ValidationError

# We expect these imports to fail or the classes to not have these fields yet
from render_tag.schema import SensorNoiseConfig, NoiseType

def test_sensor_noise_config_validation():
    """Test validation of SensorNoiseConfig."""
    
    # Test Gaussian noise
    gaussian_config = SensorNoiseConfig(
        model=NoiseType.GAUSSIAN,
        mean=0.0,
        stddev=0.05
    )
    assert gaussian_config.model == NoiseType.GAUSSIAN
    assert gaussian_config.stddev == 0.05
    
    # Test Poisson noise
    poisson_config = SensorNoiseConfig(
        model=NoiseType.POISSON
    )
    assert poisson_config.model == NoiseType.POISSON
    
    # Test Salt and Pepper
    sp_config = SensorNoiseConfig(
        model=NoiseType.SALT_AND_PEPPER,
        salt_vs_pepper=0.5,
        amount=0.02
    )
    assert sp_config.model == NoiseType.SALT_AND_PEPPER
    assert sp_config.amount == 0.02

def test_sensor_noise_defaults():
    """Test default values."""
    config = SensorNoiseConfig()
    assert config.model == NoiseType.GAUSSIAN
    assert config.mean == 0.0
    assert config.stddev == 0.0

def test_invalid_noise_params():
    """Test invalid parameters raise ValidationError."""
    with pytest.raises(ValidationError):
        SensorNoiseConfig(model=NoiseType.SALT_AND_PEPPER, amount=1.5) # Amount > 1

import numpy as np
from render_tag.backend.sensors import apply_parametric_noise

def test_apply_gaussian_noise():
    """Test application of Gaussian noise."""
    # Flat grey image
    img = np.zeros((100, 100, 3), dtype=np.uint8) + 128 
    config = SensorNoiseConfig(model=NoiseType.GAUSSIAN, mean=0.0, stddev=0.1)
    
    noisy = apply_parametric_noise(img, config)
    
    # Check that noise was added (variance should increase from 0)
    assert np.var(noisy) > 10.0 # Heuristic check
    
    # Check valid range and type
    assert noisy.min() >= 0
    assert noisy.max() <= 255
    assert noisy.dtype == np.uint8

def test_apply_salt_and_pepper():
    """Test application of Salt and Pepper noise."""
    img = np.zeros((100, 100, 3), dtype=np.uint8) + 128
    config = SensorNoiseConfig(model=NoiseType.SALT_AND_PEPPER, amount=0.1, salt_vs_pepper=0.5)
    
    noisy = apply_parametric_noise(img, config)
    
    # Check for salt (255) and pepper (0)
    # The image was 128, so 0 and 255 must come from noise
    assert np.any(noisy == 0)
    assert np.any(noisy == 255)

def test_apply_poisson_noise():
    """Test application of Poisson noise."""
    img = np.zeros((100, 100, 3), dtype=np.uint8) + 100
    config = SensorNoiseConfig(model=NoiseType.POISSON)
    
    noisy = apply_parametric_noise(img, config)
    
    # Variance check
    assert np.var(noisy) > 0
