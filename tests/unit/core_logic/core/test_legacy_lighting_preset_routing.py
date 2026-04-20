"""ACL rewrite of ``scene.lighting_preset`` to ``presets: [lighting.X]``."""

from __future__ import annotations

import pytest

from render_tag.core.config import GenConfig
from render_tag.core.schema_adapter import adapt_config


def test_emits_deprecation_warning():
    with pytest.warns(DeprecationWarning, match="scene.lighting_preset"):
        adapt_config({"scene": {"lighting_preset": "factory"}})


def test_preset_list_populated():
    with pytest.warns(DeprecationWarning):
        out = adapt_config({"scene": {"lighting_preset": "warehouse"}})
    assert out["presets"] == ["lighting.warehouse"]
    assert "lighting_preset" not in out.get("scene", {})


def test_legacy_prepends_before_explicit_presets():
    """Legacy rewrite prepends; user's explicit list wins because it's later."""
    with pytest.warns(DeprecationWarning):
        out = adapt_config(
            {
                "scene": {"lighting_preset": "factory"},
                "presets": ["lighting.warehouse"],
            }
        )
    assert out["presets"] == ["lighting.factory", "lighting.warehouse"]

    cfg = GenConfig.model_validate(out)
    # Warehouse came second → warehouse wins composition
    assert cfg.scene.lighting.intensity_max == 200.0


def test_user_value_still_beats_legacy_preset():
    with pytest.warns(DeprecationWarning):
        cfg = GenConfig.model_validate(
            adapt_config(
                {
                    "scene": {
                        "lighting_preset": "factory",
                        "lighting": {"intensity_min": 7.0},
                    },
                }
            )
        )
    assert cfg.scene.lighting.intensity_min == 7.0
    # Other factory fields come through because the user didn't override them
    assert cfg.scene.lighting.intensity_max == 400.0
