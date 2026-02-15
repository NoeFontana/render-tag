import yaml
from render_tag.core.config import load_config

def test_load_config_migrates_unversioned_yaml(tmp_path):
    """Verify that load_config automatically migrates legacy YAML files."""
    config_path = tmp_path / "legacy_config.yaml"
    # Content WITHOUT version field
    config_path.write_text("""
dataset:
  num_scenes: 5
camera:
  fov: 70.0
""")
    
    config = load_config(config_path)
    
    # Validation should pass and version should be 1.0
    assert config.version == "1.0"
    assert config.dataset.num_scenes == 5
    assert config.camera.fov == 70.0

def test_load_config_respects_explicit_version(tmp_path):
    """Verify that versioned YAML is loaded without modification."""
    config_path = tmp_path / "v1_config.yaml"
    config_path.write_text("""
version: "1.0"
dataset:
  num_scenes: 10
""")
    
    config = load_config(config_path)
    assert config.version == "1.0"
    assert config.dataset.num_scenes == 10
