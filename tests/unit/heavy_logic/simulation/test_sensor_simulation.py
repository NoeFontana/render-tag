import numpy as np

from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler, derive_iso_coupled_noise


def test_generator_samples_velocity(tmp_path):
    """Verify generator samples velocity when configured."""
    config = GenConfig()
    config.camera.velocity_mean = 1.0
    config.camera.velocity_std = 0.0  # Constant speed
    config.camera.sensor_dynamics.shutter_time_ms = 10.0

    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    recipes = recipe.cameras

    assert len(recipes) > 0
    cam = recipes[0]

    assert cam.sensor_dynamics is not None
    assert cam.sensor_dynamics.velocity is not None
    assert len(cam.sensor_dynamics.velocity) == 3
    # Magnitude should be approx 1.0
    mag = np.linalg.norm(cam.sensor_dynamics.velocity)
    assert abs(mag - 1.0) < 1e-6

    assert cam.sensor_dynamics.shutter_time_ms == 10.0


def test_generator_passes_dof_and_noise(tmp_path):
    """Verify generator passes DoF and Noise params."""
    config = GenConfig()
    config.camera.fstop = 2.8
    config.camera.focus_distance = 1.5
    config.camera.iso_noise = 0.5

    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    recipes = recipe.cameras

    cam = recipes[0]
    assert cam.fstop == 2.8
    assert cam.focus_distance == 1.5
    assert cam.iso_noise == 0.5


def test_generator_no_velocity_default(tmp_path):
    """Verify defaults are None for velocity magnitude, but Dynamics object exists."""
    config = GenConfig()
    # Defaults are 0.0

    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    recipes = recipe.cameras

    cam = recipes[0]
    # If mean/std are 0, velocity should be None
    assert cam.sensor_dynamics.velocity is None
    assert cam.fstop is None  # Default None


def test_iso_coupling_off_is_passthrough():
    """With coupling off, ISO is still cosmetic — fixtures stay bit-reproducible."""
    config = GenConfig()
    config.camera.iso = 6400
    config.camera.iso_coupling = False

    iso_noise, sensor_noise = derive_iso_coupled_noise(config.camera)
    assert iso_noise == config.camera.iso_noise  # 0.0
    assert sensor_noise is config.camera.sensor_noise  # None


def test_iso_coupling_synthesizes_noise_monotonically():
    """With coupling on, higher ISO produces strictly higher effective noise."""
    low = GenConfig()
    low.camera.iso = 100
    low.camera.iso_coupling = True

    high = GenConfig()
    high.camera.iso = 6400
    high.camera.iso_coupling = True

    low_iso_noise, low_sensor = derive_iso_coupled_noise(low.camera)
    high_iso_noise, high_sensor = derive_iso_coupled_noise(high.camera)

    assert high_iso_noise > low_iso_noise
    assert low_sensor is not None and high_sensor is not None
    assert high_sensor.stddev > low_sensor.stddev
    assert high_sensor.model == "gaussian"


def test_iso_coupling_preserves_user_overrides():
    """Explicit iso_noise or sensor_noise beats the coupling."""
    from render_tag.core.schema import SensorNoiseConfig

    config = GenConfig()
    config.camera.iso = 6400
    config.camera.iso_coupling = True
    config.camera.iso_noise = 0.25
    config.camera.sensor_noise = SensorNoiseConfig(model="gaussian", stddev=0.05)

    iso_noise, sensor_noise = derive_iso_coupled_noise(config.camera)
    assert iso_noise == 0.25
    assert sensor_noise is config.camera.sensor_noise


def test_iso_coupling_flows_into_recipe():
    """End-to-end: a compiled recipe reflects the coupled noise."""
    config = GenConfig()
    config.camera.iso = 6400
    config.camera.iso_coupling = True

    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.iso_noise is not None and cam.iso_noise > 0.0
    assert cam.sensor_noise is not None
    assert cam.sensor_noise.stddev > 0.002
    assert cam.sensor_noise.seed is not None


def test_iso_coupling_ramp_floor_clamps_to_zero():
    """ISO at or below the ramp floor produces zero iso_noise from coupling."""
    config = GenConfig()
    config.camera.iso = 100
    config.camera.iso_coupling = True

    iso_noise, _ = derive_iso_coupled_noise(config.camera)
    assert iso_noise == 0.0


def test_iso_coupling_flat_grey_variance_monotonic():
    """Flat-grey image → higher ISO yields strictly higher sampled pixel variance."""
    rng_low = np.random.default_rng(seed=0)
    rng_high = np.random.default_rng(seed=0)

    low = GenConfig()
    low.camera.iso = 100
    low.camera.iso_coupling = True
    high = GenConfig()
    high.camera.iso = 6400
    high.camera.iso_coupling = True

    _, low_noise = derive_iso_coupled_noise(low.camera)
    _, high_noise = derive_iso_coupled_noise(high.camera)
    assert low_noise is not None and high_noise is not None

    grey = np.full((128, 128), 0.5, dtype=np.float32)
    low_sample = grey + rng_low.normal(0.0, low_noise.stddev, size=grey.shape)
    high_sample = grey + rng_high.normal(0.0, high_noise.stddev, size=grey.shape)

    assert float(np.var(high_sample)) > float(np.var(low_sample))
