"""End-to-end tests for the Phase 3 lighting presets.

Mirrors ``test_sensor_presets_end_to_end.py`` — each test composes a preset
combination via the expansion pipeline, compiles a scene, and asserts the
resulting ``SceneRecipe`` reflects the preset's intent. Catches plumbing
regressions between presets → config → compiler → recipe for directional
lighting specifically.
"""

from __future__ import annotations

import math

import render_tag.core.presets  # noqa: F401  (ensures auto-registration)
from render_tag.core.config import GenConfig
from render_tag.core.presets import expand
from render_tag.core.schema_adapter import adapt_config
from render_tag.generation.compiler import SceneCompiler


def _compile_with_presets(preset_names: list[str]) -> GenConfig:
    data = {"presets": preset_names}
    return GenConfig.model_validate(adapt_config(data))


def _suns(recipe) -> list:
    return [light for light in recipe.world.lights if light.type == "SUN"]


def test_shadow_directional_hard_emits_one_sun():
    config = _compile_with_presets(["lighting.outdoor_industrial", "shadow.directional_hard"])
    recipe = SceneCompiler(config, global_seed=42).compile_scene(0)

    suns = _suns(recipe)
    assert len(suns) == 1
    # Outdoor intensity range survives from lighting.outdoor_industrial
    point_intensities = [light.intensity for light in recipe.world.lights if light.type == "POINT"]
    # /3 because compiler divides by num_lights, so 800/3 ≤ each ≤ 1200/3
    assert all(200.0 <= i <= 450.0 for i in point_intensities)


def test_lighting_low_key_composed_with_industrial_dr_clips_to_black_path():
    """Composition pins both lighting floor AND sensor DR/tone-mapping in the recipe."""
    config = _compile_with_presets(["lighting.low_key", "sensor.industrial_dr"])
    recipe = SceneCompiler(config, global_seed=42).compile_scene(0)

    cam = recipe.cameras[0]
    assert cam.dynamic_range_db == 60.0
    assert cam.tone_mapping == "linear"

    # Low intensity — each point light between 20/3 and 80/3 per the compiler divide
    point_intensities = [light.intensity for light in recipe.world.lights if light.type == "POINT"]
    assert all(6.0 <= i <= 27.0 for i in point_intensities)

    suns = _suns(recipe)
    assert len(suns) == 1
    assert math.isclose(suns[0].intensity, 2.0, abs_tol=1e-9)


def test_lighting_mixed_temperature_emits_two_distinct_suns():
    config = _compile_with_presets(["lighting.mixed_temperature"])
    recipe = SceneCompiler(config, global_seed=42).compile_scene(0)

    suns = _suns(recipe)
    assert len(suns) == 2
    warm, cool = sorted(suns, key=lambda s: -s.color[0])  # warm has higher R
    assert warm.color == [1.0, 0.7, 0.4]
    assert cool.color == [0.8, 0.9, 1.0]


def test_directional_hard_list_preserved_through_expand():
    """Expand-pass must not flatten a list-valued ``directional``."""
    out = expand({"presets": ["lighting.mixed_temperature"]})
    directional = out["scene"]["lighting"]["directional"]
    assert isinstance(directional, list)
    assert len(directional) == 2


def test_composition_order_shadow_overrides_lighting():
    """Left-to-right merge: ``shadow.directional_hard`` last means its directional wins."""
    out = expand({"presets": ["lighting.mixed_temperature", "shadow.directional_hard"]})
    directional = out["scene"]["lighting"]["directional"]
    # The single-dict directional from shadow.directional_hard replaces the list
    assert isinstance(directional, dict)
    assert math.isclose(directional["azimuth"], 0.785398, abs_tol=1e-6)
