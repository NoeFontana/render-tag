import numpy as np
import pytest

from render_tag.backend.tonemap import apply_tone_mapping
from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler


@pytest.fixture
def flat_grey_uint8() -> np.ndarray:
    return np.full((64, 64, 3), 128, dtype=np.uint8)


def test_filmic_is_passthrough(flat_grey_uint8):
    """Default mode must not mutate pixels so existing fixtures stay bit-exact."""
    out = apply_tone_mapping(flat_grey_uint8, "filmic")
    assert np.array_equal(out, flat_grey_uint8)


def test_linear_and_srgb_differ_from_filmic(flat_grey_uint8):
    """srgb and linear must produce measurably different pixels from filmic."""
    filmic = apply_tone_mapping(flat_grey_uint8, "filmic")
    srgb = apply_tone_mapping(flat_grey_uint8, "srgb")
    linear = apply_tone_mapping(flat_grey_uint8, "linear")

    assert np.any(np.abs(srgb.astype(int) - filmic.astype(int)) >= 1)
    assert np.any(np.abs(linear.astype(int) - filmic.astype(int)) >= 1)
    assert np.any(np.abs(srgb.astype(int) - linear.astype(int)) >= 1)


def test_tone_mapping_preserves_shape_and_dtype(flat_grey_uint8):
    for mode in ("linear", "srgb", "filmic"):
        out = apply_tone_mapping(flat_grey_uint8, mode)
        assert out.shape == flat_grey_uint8.shape
        assert out.dtype == flat_grey_uint8.dtype


def test_unknown_mode_raises(flat_grey_uint8):
    with pytest.raises(ValueError):
        apply_tone_mapping(flat_grey_uint8, "aces")  # type: ignore[arg-type]


def test_tone_mapping_float_input_stays_float():
    gradient = np.linspace(0.0, 1.0, 64, dtype=np.float32).reshape(8, 8)
    out = apply_tone_mapping(gradient, "srgb")
    assert out.dtype == np.float32
    assert out.shape == gradient.shape


def test_tone_mapping_flows_into_recipe():
    """End-to-end: a compiled recipe reflects the configured tone_mapping."""
    config = GenConfig()
    config.camera.tone_mapping = "linear"

    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.tone_mapping == "linear"


def test_tone_mapping_default_is_filmic_in_recipe():
    config = GenConfig()
    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.tone_mapping == "filmic"
