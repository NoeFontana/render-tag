"""End-to-end tests for sensor presets.

Each test composes a preset via the preset-expansion pipeline, validates it
through ``GenConfig``, compiles a scene, and asserts the resulting
``CameraRecipe`` reflects the preset's intent. Catches plumbing regressions
between presets → config → compiler → recipe.
"""

from __future__ import annotations

import render_tag.core.presets  # noqa: F401  (ensures auto-registration)
from render_tag.core.config import GenConfig
from render_tag.core.presets import expand
from render_tag.core.schema_adapter import adapt_config
from render_tag.generation.compiler import SceneCompiler


def _compile_with_presets(preset_names: list[str]) -> GenConfig:
    data = {"presets": preset_names}
    return GenConfig.model_validate(adapt_config(data))


def test_industrial_dr_preset_reaches_camera_recipe():
    config = _compile_with_presets(["sensor.industrial_dr"])
    recipe = SceneCompiler(config, global_seed=42).compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.dynamic_range_db == 60.0
    assert cam.tone_mapping == "linear"


def test_raw_pipeline_preset_reaches_camera_recipe():
    config = _compile_with_presets(["sensor.raw_pipeline"])
    recipe = SceneCompiler(config, global_seed=42).compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.tone_mapping == "linear"
    assert cam.sensor_noise is not None
    assert cam.sensor_noise.models is not None
    assert len(cam.sensor_noise.models) == 2
    assert cam.sensor_noise.models[0].model == "poisson"
    assert cam.sensor_noise.models[1].model == "gaussian"


def test_hdr_sweep_plus_industrial_dr_composition():
    """Composition lets one benchmark stack low-DR onto the HDR ISO sweep."""
    config = _compile_with_presets(["sensor.hdr_sweep", "sensor.industrial_dr"])
    recipe = SceneCompiler(config, global_seed=42).compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.dynamic_range_db == 60.0
    assert cam.tone_mapping == "linear"
    # hdr_sweep's sensor_noise floor survives since industrial_dr doesn't touch it
    assert cam.sensor_noise is not None
    assert cam.sensor_noise.model == "gaussian"


def test_raw_pipeline_preserves_stacked_noise_through_expand():
    """The preset-expand pass must not flatten the `models` list."""
    out = expand({"presets": ["sensor.raw_pipeline"]})
    models = out["camera"]["sensor_noise"]["models"]
    assert isinstance(models, list)
    assert [m["model"] for m in models] == ["poisson", "gaussian"]
