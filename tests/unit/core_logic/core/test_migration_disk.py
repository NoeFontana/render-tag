import json

import pytest
import yaml

from render_tag.core.config import load_config
from render_tag.core.schema.job import JobSpec


def test_load_config_does_not_rewrite_file(tmp_path):
    """load_config migrates in memory only; the on-disk file is left alone."""
    config_path = tmp_path / "legacy.yaml"
    original = "dataset: {num_scenes: 1}\ncamera: {fov: 60.0}\n"
    config_path.write_text(original)

    load_config(config_path)

    assert config_path.read_text() == original


def test_job_spec_from_file_does_not_rewrite_file(tmp_path):
    """JobSpec.from_file migrates in memory only; the on-disk file is left alone."""
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
            "scene": {},
            "physics": {},
            "scenario": {},
            "renderer": {},
        },
    }
    with open(job_path, "w") as f:
        json.dump(legacy_data, f)

    with pytest.warns(DeprecationWarning):
        JobSpec.from_file(job_path)

    with open(job_path) as f:
        on_disk = json.load(f)
    assert on_disk["scene_config"]["tag"] == {"family": "tag36h11", "size_meters": 0.1}


def test_cli_migrate_rewrites_yaml_on_disk(tmp_path):
    """`render-tag config migrate --write` is the documented way to upgrade disk files."""
    from typer.testing import CliRunner

    from render_tag.cli.main import app

    config_path = tmp_path / "legacy.yaml"
    config_path.write_text("dataset: {num_scenes: 1}\ncamera: {fov: 60.0}\n")

    result = CliRunner().invoke(app, ["config", "migrate", str(config_path), "--write"])
    assert result.exit_code == 0, result.output

    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["version"] == "0.2"
