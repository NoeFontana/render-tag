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
