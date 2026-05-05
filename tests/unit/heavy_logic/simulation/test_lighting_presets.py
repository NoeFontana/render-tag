"""Lighting preset routing through the modern ``presets:`` list.

The legacy ``scene.lighting_preset`` enum was retired at 1.0 together with
the ACL rewrite rule. This test ensures the first-class preset path keeps
producing the same LightingConfig values users had under the legacy field.
"""

from __future__ import annotations

from render_tag.core.config import GenConfig
from render_tag.core.schema_adapter import adapt_config


def test_modern_presets_list_applies_lighting_preset():
    cfg = GenConfig.model_validate(adapt_config({"presets": ["lighting.outdoor_industrial"]}))
    assert cfg.scene.lighting.intensity_min == 150.0
    assert cfg.scene.lighting.intensity_max == 400.0
    assert cfg.scene.lighting.radius_max <= 0.05
    assert len(cfg.scene.lighting.directional) == 1
    assert cfg.scene.lighting.directional[0].intensity == 35.0
    assert cfg.presets == ["lighting.outdoor_industrial"]


def test_outdoor_sun_preset_values():
    cfg = GenConfig.model_validate(adapt_config({"presets": ["lighting.outdoor_sun"]}))
    assert cfg.scene.lighting.intensity_min == 50.0
    assert cfg.scene.lighting.intensity_max == 200.0
    assert cfg.scene.lighting.radius_max == 0.0
    assert len(cfg.scene.lighting.directional) == 1
    assert cfg.scene.lighting.directional[0].intensity == 30.0


def test_factory_preset_values():
    cfg = GenConfig.model_validate(adapt_config({"presets": ["lighting.factory"]}))
    assert cfg.scene.lighting.intensity_min == 200.0
    assert cfg.scene.lighting.intensity_max == 400.0


def test_warehouse_preset_values():
    cfg = GenConfig.model_validate(adapt_config({"presets": ["lighting.warehouse"]}))
    assert cfg.scene.lighting.intensity_min == 50.0
    assert cfg.scene.lighting.intensity_max == 200.0
