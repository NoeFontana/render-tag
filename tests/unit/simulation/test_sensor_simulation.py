
import numpy as np

from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler


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
