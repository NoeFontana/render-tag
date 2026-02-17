import json

from render_tag.core.schema.job import JobSpec


def test_job_spec_from_json_migrates_legacy(tmp_path):
    """Verify that JobSpec.from_json handles legacy JSON strings."""
    legacy_data = {
        "job_id": "job-456",
        "global_seed": 42,
        "env_hash": "hash",
        "blender_version": "4.2.0",
        "paths": {"output_dir": ".", "logs_dir": ".", "assets_dir": "."},
        "scene_config": {
            "version": "0.1",
            "dataset": {"num_scenes": 1},
            "camera": {"resolution": [100, 100]},
            "tag": {"family": "tag36h11", "size_meters": 0.1},
            "scene": {},
            "physics": {},
            "scenario": {},
            "renderer": {},
        },
    }
    json_str = json.dumps(legacy_data)

    spec = JobSpec.from_json(json_str)
    assert spec.version == "0.2"
    assert spec.job_id == "job-456"


def test_job_spec_includes_version_field():
    """Verify that new JobSpecs have the version field."""
    from pathlib import Path

    from render_tag.core.config import GenConfig
    from render_tag.core.schema.job import JobInfrastructure, JobPaths

    paths = JobPaths(output_dir=Path("."), logs_dir=Path("."), assets_dir=Path("."))
    spec = JobSpec(
        job_id="test",
        paths=paths,
        infrastructure=JobInfrastructure(),
        global_seed=42,
        scene_config=GenConfig(version="0.1"),
        env_hash="h",
        blender_version="v",
        version="0.1",
    )

    assert spec.version == "0.1"
