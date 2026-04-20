import numpy as np

from render_tag.backend.dynamic_range import apply_sensor_dr
from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler


def _gradient_uint8() -> np.ndarray:
    row = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    grid = np.tile(row, (16, 1))
    return np.round(grid * 255.0).astype(np.uint8)


def test_none_is_passthrough():
    img = _gradient_uint8()
    assert np.array_equal(apply_sensor_dr(img, None), img)


def test_zero_db_is_passthrough():
    img = _gradient_uint8()
    assert np.array_equal(apply_sensor_dr(img, 0.0), img)


def test_low_dr_raises_shadow_floor_uint8():
    """At 40 dB the floor exceeds 1 LSB; 120 dB's floor is sub-LSB."""
    img = _gradient_uint8()
    high_dr = apply_sensor_dr(img, 120.0)
    low_dr = apply_sensor_dr(img, 40.0)

    assert int(low_dr.min()) > int(high_dr.min())


def test_low_dr_raises_shadow_floor_float():
    """Float precision exposes the floor even at 60 dB."""
    grad = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    high = apply_sensor_dr(grad, 120.0)
    low = apply_sensor_dr(grad, 60.0)

    assert float(low.min()) > float(high.min())
    assert float(low.min()) > 0.0


def test_high_dr_preserves_shadows():
    """At 120 dB the floor is below 1 LSB, so darkest pixel stays ~0."""
    img = _gradient_uint8()
    out = apply_sensor_dr(img, 120.0)
    assert int(out.min()) <= 1


def test_saturation_caps_at_full_scale():
    img = np.full((8, 8, 3), 255, dtype=np.uint8)
    out = apply_sensor_dr(img, 60.0)
    assert int(out.max()) == 255


def test_float_input_stays_float():
    grad = np.linspace(0.0, 1.0, 64, dtype=np.float32).reshape(8, 8)
    out = apply_sensor_dr(grad, 60.0)
    assert out.dtype == np.float32
    assert float(out.min()) > 0.0


def test_dynamic_range_flows_into_recipe():
    config = GenConfig()
    config.camera.dynamic_range_db = 60.0

    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.dynamic_range_db == 60.0


def test_dynamic_range_default_none_in_recipe():
    """CameraConfig defaults 120.0, but the recipe must reflect that faithfully."""
    config = GenConfig()
    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.dynamic_range_db == 120.0
