import numpy as np
import pytest
from render_tag.config import GenConfig
from render_tag.generator import Generator


def test_generator_samples_velocity(tmp_path):
    """Verify generator samples velocity when configured."""
    config = GenConfig()
    config.camera.velocity_mean = 1.0
    config.camera.velocity_std = 0.0  # Constant speed
    config.camera.shutter_time_ms = 10.0

    gen = Generator(config, output_dir=tmp_path)

    recipes = gen._generate_camera_recipes()

    assert len(recipes) > 0
    cam = recipes[0]

    assert cam.velocity is not None
    assert len(cam.velocity) == 3
    # Magnitude should be approx 1.0
    mag = np.linalg.norm(cam.velocity)
    assert abs(mag - 1.0) < 1e-6

    assert cam.shutter_time_ms == 10.0


def test_generator_passes_dof_and_noise(tmp_path):
    """Verify generator passes DoF and Noise params."""
    config = GenConfig()
    config.camera.fstop = 2.8
    config.camera.focus_distance = 1.5
    config.camera.iso_noise = 0.5

    gen = Generator(config, output_dir=tmp_path)
    recipes = gen._generate_camera_recipes()

    cam = recipes[0]
    assert cam.fstop == 2.8
    assert cam.focus_distance == 1.5
    assert cam.iso_noise == 0.5


def test_generator_no_velocity_default(tmp_path):
    """Verify defaults are None."""
    config = GenConfig()
    # Defaults are 0.0

    gen = Generator(config, output_dir=tmp_path)
    recipes = gen._generate_camera_recipes()

    cam = recipes[0]
    # If mean/std are 0, velocity should be None
    assert cam.velocity is None
    assert cam.fstop is None  # Default None
