"""Regression bridge: new preset path matches the old enum path bit-for-bit.

The pre-refactor behavior ran ``SceneConfig.lighting = get_lighting_preset(X)``
inside a Pydantic validator. The new behavior routes ``scene.lighting_preset``
through the ACL to ``presets: [lighting.X]``. For each of the three existing
enum values, the resolved ``SceneConfig.lighting`` must be identical — this
guards every existing YAML that uses ``lighting_preset: ...``.
"""

from __future__ import annotations

import warnings

import pytest

from render_tag.core.config import GenConfig, LightingPreset, get_lighting_preset
from render_tag.core.schema_adapter import adapt_config


@pytest.mark.parametrize(
    "enum_value, preset_name",
    [
        (LightingPreset.FACTORY, "lighting.factory"),
        (LightingPreset.WAREHOUSE, "lighting.warehouse"),
        (LightingPreset.OUTDOOR_INDUSTRIAL, "lighting.outdoor_industrial"),
    ],
)
def test_legacy_enum_equals_presets_list(enum_value: LightingPreset, preset_name: str) -> None:
    legacy_data = {"scene": {"lighting_preset": enum_value.value}}
    new_data = {"presets": [preset_name]}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy_cfg = GenConfig.model_validate(adapt_config(legacy_data))
    new_cfg = GenConfig.model_validate(adapt_config(new_data))

    assert legacy_cfg.scene.lighting.model_dump() == new_cfg.scene.lighting.model_dump()
    expected = get_lighting_preset(enum_value).model_dump()
    assert new_cfg.scene.lighting.model_dump() == expected
