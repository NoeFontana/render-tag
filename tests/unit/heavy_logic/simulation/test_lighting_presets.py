"""Lighting preset routing through the ACL."""

from __future__ import annotations

import warnings

from render_tag.core.config import (
    GenConfig,
    LightingConfig,
    LightingPreset,
    get_lighting_preset,
)
from render_tag.core.schema_adapter import adapt_config


def test_lighting_presets_exist():
    factory = get_lighting_preset(LightingPreset.FACTORY)
    assert isinstance(factory, LightingConfig)
    assert factory.intensity_min >= 200
    assert factory.radius_min >= 0.1

    warehouse = get_lighting_preset(LightingPreset.WAREHOUSE)
    assert isinstance(warehouse, LightingConfig)
    assert warehouse.intensity_max <= 300

    outdoor = get_lighting_preset(LightingPreset.OUTDOOR_INDUSTRIAL)
    assert isinstance(outdoor, LightingConfig)
    assert outdoor.intensity_min >= 800
    assert outdoor.radius_max <= 0.05


def test_legacy_lighting_preset_routes_through_acl():
    """Legacy ``scene.lighting_preset`` is rewritten to ``presets: [lighting.X]``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        cfg = GenConfig.model_validate(adapt_config({"scene": {"lighting_preset": "factory"}}))
    assert cfg.scene.lighting.intensity_min == 200.0
    assert cfg.presets == ["lighting.factory"]


def test_modern_presets_list_applies_preset():
    cfg = GenConfig.model_validate(adapt_config({"presets": ["lighting.outdoor_industrial"]}))
    assert cfg.scene.lighting.intensity_min == 800.0
    assert cfg.presets == ["lighting.outdoor_industrial"]
