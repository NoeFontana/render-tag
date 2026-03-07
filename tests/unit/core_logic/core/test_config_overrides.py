
import pytest
from pathlib import Path
from render_tag.core.config_loader import ConfigResolver
from render_tag.core.config import GenConfig

def test_dot_notation_overrides():
    resolver = ConfigResolver()
    
    # Test simple nesting
    overrides = {"camera.fov": 90.0}
    spec = resolver.resolve(output_dir=Path("/tmp/out"), overrides=overrides)
    assert spec.scene_config.camera.fov == 90.0
    
    # Test deeper nesting
    overrides = {"camera.intrinsics.k1": 0.123}
    spec = resolver.resolve(output_dir=Path("/tmp/out"), overrides=overrides)
    assert spec.scene_config.camera.intrinsics.k1 == 0.123
    
    # Test list indexing
    # Note: GenConfig doesn't have many lists, but evaluation_scopes is one.
    # However, setting a list element might be tricky if it's an Enum.
    # Let's try something that exists. resolution is a tuple.
    overrides = {"camera.resolution": [1280, 720]}
    spec = resolver.resolve(output_dir=Path("/tmp/out"), overrides=overrides)
    assert spec.scene_config.camera.resolution == (1280, 720)

def test_dot_notation_list_index():
    resolver = ConfigResolver()
    # Test indexing if we had a list of cameras (we don't yet in GenConfig, but requirement mentioned it)
    # Actually, GenConfig has:
    # scenario: ScenarioConfig
    #   tag_families: list[TagFamily]
    
    from render_tag.core.config import TagFamily
    overrides = {"scenario.tag_families.0": "tag16h5"}
    spec = resolver.resolve(output_dir=Path("/tmp/out"), overrides=overrides)
    assert spec.scene_config.scenario.tag_families[0] == TagFamily.TAG16H5

def test_invalid_override_path():
    resolver = ConfigResolver()
    overrides = {"camera.non_existent_field": 10}
    with pytest.raises(AttributeError):
        resolver.resolve(output_dir=Path("/tmp/out"), overrides=overrides)

def test_type_coercion():
    resolver = ConfigResolver()
    # Pydantic should handle coercion if we pass strings from CLI
    overrides = {"camera.fov": "85.5"}
    spec = resolver.resolve(output_dir=Path("/tmp/out"), overrides=overrides)
    assert spec.scene_config.camera.fov == 85.5
    assert isinstance(spec.scene_config.camera.fov, float)
