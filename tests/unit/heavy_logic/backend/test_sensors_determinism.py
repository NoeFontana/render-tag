import numpy as np

from render_tag.backend.sensors import apply_parametric_noise


def test_noise_is_isolated_from_global_state():
    """Verify that current noise application is NOT affected by global numpy seed."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    # NO seed provided in config -> should be non-deterministic but isolated
    from render_tag.core.schema import NoiseType, SensorNoiseConfig

    config = SensorNoiseConfig(model=NoiseType.GAUSSIAN, mean=0.0, stddev=0.1)

    # Run 1
    np.random.seed(42)
    noisy1 = apply_parametric_noise(image, config)

    # Run 2 (Same global seed)
    np.random.seed(42)
    noisy2 = apply_parametric_noise(image, config)

    # Since we use default_rng(None), these should now be DIFFERENT
    # because they are both non-deterministic and independent of global seed.
    assert not np.array_equal(noisy1, noisy2)


def test_noise_application_accepts_seed():
    """Verify that we can pass a seed to ensure isolation from global state."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    # We WANT the config to support a seed
    from render_tag.core.schema import NoiseType, SensorNoiseConfig

    config = SensorNoiseConfig(model=NoiseType.GAUSSIAN, mean=0.0, stddev=0.1, seed=123)

    # This should fail if the implementation doesn't use the seed
    np.random.seed(42)  # Set global seed to something else
    noisy1 = apply_parametric_noise(image, config)

    np.random.seed(99)  # Change global seed
    noisy2 = apply_parametric_noise(image, config)

    # If it correctly uses the seed from config, these should be equal regardless of global state
    assert np.array_equal(noisy1, noisy2)
