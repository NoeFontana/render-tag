"""Tests for ``core.presets.pipeline.expand``."""

from __future__ import annotations

import pytest

from render_tag.core.presets import expand
from render_tag.core.presets.base import Preset, PresetRegistry


def _reg() -> PresetRegistry:
    reg = PresetRegistry()
    reg.register(
        Preset(
            name="scene.bright",
            description="",
            version="1.0",
            override=lambda: {
                "scene": {"lighting": {"intensity_min": 200.0, "intensity_max": 400.0}}
            },
        )
    )
    reg.register(
        Preset(
            name="scene.harsh",
            description="",
            version="1.0",
            override=lambda: {"scene": {"lighting": {"radius_min": 0.0, "radius_max": 0.02}}},
        )
    )
    reg.register(
        Preset(
            name="scopes.calibration",
            description="",
            version="1.0",
            override=lambda: {"dataset": {"evaluation_scopes": ["CALIBRATION"]}},
        )
    )
    return reg


def test_no_presets_key_is_identity():
    data = {"scene": {"lighting": {"intensity_min": 10.0}}}
    assert expand(dict(data), registry=_reg()) == data


def test_single_preset_applied():
    out = expand({"presets": ["scene.bright"]}, registry=_reg())
    assert out["scene"]["lighting"]["intensity_min"] == 200.0
    assert out["presets"] == ["scene.bright"]


def test_two_presets_compose_later_wins():
    out = expand(
        {"presets": ["scene.bright", "scene.harsh"]},
        registry=_reg(),
    )
    # bright set intensity; harsh added radius
    assert out["scene"]["lighting"]["intensity_min"] == 200.0
    assert out["scene"]["lighting"]["radius_max"] == 0.02


def test_user_value_beats_preset():
    out = expand(
        {
            "presets": ["scene.bright"],
            "scene": {"lighting": {"intensity_min": 5.0}},
        },
        registry=_reg(),
    )
    # preset supplied 200, user supplied 5 → user wins
    assert out["scene"]["lighting"]["intensity_min"] == 5.0
    # untouched preset keys persist
    assert out["scene"]["lighting"]["intensity_max"] == 400.0


def test_list_of_strings_concatenates_across_presets_and_user():
    out = expand(
        {
            "presets": ["scopes.calibration"],
            "dataset": {"evaluation_scopes": ["DETECTION"]},
        },
        registry=_reg(),
    )
    assert out["dataset"]["evaluation_scopes"] == ["CALIBRATION", "DETECTION"]


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        expand({"presets": ["does.not.exist"]}, registry=_reg())


def test_presets_must_be_list():
    with pytest.raises(ValueError, match="must be a list"):
        expand({"presets": "scene.bright"}, registry=_reg())


def test_sensor_hdr_sweep_applies_realistic_sensor_profile():
    """sensor.hdr_sweep enables ISO coupling and supplies a parametric noise floor."""
    import render_tag.core.presets  # noqa: F401  (ensures auto-registration)
    from render_tag.core.presets.base import default_registry

    out = expand({"presets": ["sensor.hdr_sweep"]}, registry=default_registry)
    camera = out["camera"]
    assert camera["iso"] == 800
    assert camera["iso_coupling"] is True
    assert camera["sensor_noise"]["model"] == "gaussian"
    assert camera["sensor_noise"]["stddev"] > 0.0


def test_sensor_hdr_sweep_lets_user_iso_override_preset():
    """A benchmark composing sensor.hdr_sweep can still crank ISO past the preset default."""
    import render_tag.core.presets  # noqa: F401
    from render_tag.core.presets.base import default_registry

    out = expand(
        {
            "presets": ["sensor.hdr_sweep"],
            "camera": {"iso": 3200},
        },
        registry=default_registry,
    )
    assert out["camera"]["iso"] == 3200
    # Preset's other keys persist.
    assert out["camera"]["iso_coupling"] is True
    assert out["camera"]["sensor_noise"]["stddev"] > 0.0


def test_sensor_industrial_dr_sets_low_dr_and_linear_tonemap():
    """sensor.industrial_dr models a low-DR industrial sensor for outdoor stress."""
    import render_tag.core.presets  # noqa: F401
    from render_tag.core.presets.base import default_registry

    out = expand({"presets": ["sensor.industrial_dr"]}, registry=default_registry)
    camera = out["camera"]
    assert camera["dynamic_range_db"] == 60.0
    assert camera["tone_mapping"] == "linear"
    assert camera["iso_coupling"] is True


def test_sensor_raw_pipeline_stacks_poisson_and_gaussian():
    """sensor.raw_pipeline expresses shot + read noise as a stacked pipeline."""
    import render_tag.core.presets  # noqa: F401
    from render_tag.core.presets.base import default_registry

    out = expand({"presets": ["sensor.raw_pipeline"]}, registry=default_registry)
    camera = out["camera"]
    assert camera["tone_mapping"] == "linear"
    assert camera["iso_coupling"] is False
    models = camera["sensor_noise"]["models"]
    assert [m["model"] for m in models] == ["poisson", "gaussian"]


def test_sensor_industrial_dr_composes_with_hdr_sweep():
    """Stacking sensor.hdr_sweep then sensor.industrial_dr yields a composite profile."""
    import render_tag.core.presets  # noqa: F401
    from render_tag.core.presets.base import default_registry

    out = expand(
        {"presets": ["sensor.hdr_sweep", "sensor.industrial_dr"]},
        registry=default_registry,
    )
    camera = out["camera"]
    # industrial_dr overrides iso to 400; keeps hdr_sweep's sensor_noise profile.
    assert camera["iso"] == 400
    assert camera["dynamic_range_db"] == 60.0
    assert camera["tone_mapping"] == "linear"
    assert camera["sensor_noise"]["model"] == "gaussian"
