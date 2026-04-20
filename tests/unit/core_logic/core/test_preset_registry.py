"""Tests for the preset registry primitives."""

from __future__ import annotations

import pytest

from render_tag.core.presets.base import Preset, PresetRegistry, register_preset


def test_register_and_get():
    reg = PresetRegistry()
    preset = Preset(
        name="demo.one",
        description="d",
        version="1.0",
        override=lambda: {"a": 1},
    )
    reg.register(preset)
    assert reg.get("demo.one") is preset


def test_duplicate_registration_rejected():
    reg = PresetRegistry()
    preset = Preset(name="demo.one", description="d", version="1.0", override=dict)
    reg.register(preset)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(preset)


def test_unknown_name_raises():
    reg = PresetRegistry()
    with pytest.raises(KeyError, match="Unknown preset"):
        reg.get("nope.nope")


@pytest.mark.parametrize(
    "bad",
    ["no_dot", "Upper.case", "lighting.Factory", "1digit.start", "x.", ".y", "a.b.c"],
)
def test_invalid_name_rejected(bad: str):
    reg = PresetRegistry()
    preset = Preset(name=bad, description="d", version="1.0", override=dict)
    with pytest.raises(ValueError, match="Invalid preset name"):
        reg.register(preset)


def test_names_sorted():
    reg = PresetRegistry()
    for n in ("lighting.factory", "evaluation.calibration_full", "shadow.harsh"):
        reg.register(Preset(name=n, description="d", version="1.0", override=dict))
    assert reg.names() == ["evaluation.calibration_full", "lighting.factory", "shadow.harsh"]


def test_by_category_groups():
    reg = PresetRegistry()
    for n in ("lighting.factory", "lighting.warehouse", "shadow.harsh"):
        reg.register(Preset(name=n, description="d", version="1.0", override=dict))
    grouped = reg.by_category()
    assert list(grouped) == ["lighting", "shadow"]
    assert [p.name for p in grouped["lighting"]] == ["lighting.factory", "lighting.warehouse"]


def test_decorator_registers_on_import():
    reg = PresetRegistry()

    @register_preset(name="demo.two", description="x", registry=reg)
    def _override() -> dict:
        return {"foo": "bar"}

    assert reg.get("demo.two").override() == {"foo": "bar"}


def test_default_registry_has_builtins():
    from render_tag.core.presets import default_registry

    names = default_registry.names()
    for expected in (
        "evaluation.calibration_full",
        "lighting.factory",
        "lighting.outdoor_industrial",
        "lighting.warehouse",
        "sensor.hdr_sweep",
        "shadow.harsh",
    ):
        assert expected in names, f"missing {expected}"
