import json
import yaml
from pathlib import Path
from render_tag.core.config import load_config
from render_tag.core.schema.job import JobSpec

def test_load_config_upgrades_yaml_on_disk(tmp_path):
    """Verify that load_config overwrites legacy YAML with versioned content."""
    config_path = tmp_path / "legacy.yaml"
    config_path.write_text("dataset: {num_scenes: 1}\ncamera: {fov: 60.0}")
    
    # Load it
    load_config(config_path)
    
    # Check disk content
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["version"] == "0.1"

def test_job_spec_from_file_upgrades_json_on_disk(tmp_path):
    """Verify that JobSpec.from_file overwrites legacy JSON with versioned content."""
    job_path = tmp_path / "legacy_job.json"
    legacy_data = {
        "job_id": "leg-1",
        "global_seed": 1,
        "env_hash": "h",
        "blender_version": "v",
        "paths": {"output_dir": ".", "logs_dir": ".", "assets_dir": "."},
        "scene_config": {
            "version": "0.1",
            "dataset": {"num_scenes": 1},
            "camera": {"resolution": [100, 100]},
            "tag": {"family": "tag36h11", "size_meters": 0.1},
            "scene": {}, "physics": {}, "scenario": {}, "renderer": {}
        }
    }
    with open(job_path, "w") as f:
        json.dump(legacy_data, f)
        
    # Load it
    JobSpec.from_file(job_path)
    
    # Check disk content
    with open(job_path) as f:
        data = json.load(f)
    assert data["version"] == "0.1"
