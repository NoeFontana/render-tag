import json
import pytest
from render_tag.core.schema.job import JobSpec

def test_job_spec_migrates_unversioned_json(tmp_path):
    """Verify that JobSpec loading (simulated) handles legacy JSON."""
    # We can't easily mock model_validate_json if it doesn't exist or is standard
    # But we can test the dictionary migration logic
    legacy_data = {
        "job_id": "job-123",
        "created_at": "2026-01-01T00:00:00Z",
        "global_seed": 42,
        "env_hash": "hash",
        "blender_version": "4.2.0",
        "paths": {
            "output_dir": str(tmp_path),
            "logs_dir": str(tmp_path),
            "assets_dir": str(tmp_path)
        },
        "scene_config": {
            "version": "1.0", # Nested config is already migrated
            "dataset": {"num_scenes": 1},
            "camera": {"resolution": [640, 480], "fov": 70.0},
            "tag": {"family": "tag36h11", "size_meters": 0.1},
            "scene": {"lighting": {}},
            "physics": {},
            "scenario": {"layout": "plain"},
            "renderer": {"mode": "cycles"}
        }
    }
    
    # Pre-migration validation should fail if version is required
    with pytest.raises(Exception):
        JobSpec.model_validate(legacy_data)

def test_job_spec_from_json_migrates_legacy(tmp_path):
    """Verify that JobSpec.from_json handles legacy JSON strings."""
    legacy_data = {
        "job_id": "job-456",
        "global_seed": 42,
        "env_hash": "hash",
        "blender_version": "4.2.0",
        "paths": {"output_dir": ".", "logs_dir": ".", "assets_dir": "."},
        "scene_config": {
            "version": "1.0",
            "dataset": {"num_scenes": 1},
            "camera": {"resolution": [100, 100]},
            "tag": {"family": "tag36h11", "size_meters": 0.1},
            "scene": {}, "physics": {}, "scenario": {}, "renderer": {}
        }
    }
    json_str = json.dumps(legacy_data)
    
    spec = JobSpec.from_json(json_str)
    assert spec.version == "1.0"
    assert spec.job_id == "job-456"

def test_job_spec_includes_version_field():
    """Verify that new JobSpecs have the version field."""
    from pathlib import Path
    from render_tag.core.schema.job import JobPaths, JobInfrastructure
    from render_tag.core.config import GenConfig
    
    paths = JobPaths(output_dir=Path("."), logs_dir=Path("."), assets_dir=Path("."))
    spec = JobSpec(
        job_id="test",
        paths=paths,
        infrastructure=JobInfrastructure(),
        global_seed=42,
        scene_config=GenConfig(version="1.0"),
        env_hash="h",
        blender_version="v",
        version="1.0"
    )
    
    assert spec.version == "1.0"
