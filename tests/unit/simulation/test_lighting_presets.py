from render_tag.core.config import LightingConfig, LightingPreset, SceneConfig, get_lighting_preset


def test_lighting_presets_exist():
    """Verify lighting presets are defined."""
    # Factory: Bright, soft shadows (diffuse light)
    factory = get_lighting_preset(LightingPreset.FACTORY)
    assert isinstance(factory, LightingConfig)
    assert factory.intensity_min >= 200
    assert factory.radius_min >= 0.1

    # Warehouse: Dimmer, potentially harder shadows
    warehouse = get_lighting_preset(LightingPreset.WAREHOUSE)
    assert isinstance(warehouse, LightingConfig)
    assert warehouse.intensity_max <= 300

    # Outdoor: Very bright, hard shadows (sun)
    outdoor = get_lighting_preset(LightingPreset.OUTDOOR_INDUSTRIAL)
    assert isinstance(outdoor, LightingConfig)
    assert outdoor.intensity_min >= 800
    assert outdoor.radius_max <= 0.05  # Sun is small/hard source relative to sky


def test_scene_config_applies_preset():
    """Verify SceneConfig applies lighting preset."""
    # Create config with preset
    config = SceneConfig(lighting_preset=LightingPreset.FACTORY)

    # Check that lighting config matches factory preset
    # Default intensity_min is 50. Factory is 200.
    assert config.lighting.intensity_min == 200.0

    # Ensure it works for other presets
    config = SceneConfig(lighting_preset=LightingPreset.OUTDOOR_INDUSTRIAL)
    assert config.lighting.intensity_min == 800.0
