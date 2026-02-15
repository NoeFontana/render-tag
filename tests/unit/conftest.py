import hashlib

import pytest

from render_tag.core.config import GenConfig
from render_tag.core.schema.job import JobPaths, JobSpec, calculate_job_id


@pytest.fixture
def mock_gen_config():
    """Returns a valid GenConfig with default values."""
    config = GenConfig()
    # Ensure sane defaults for testing
    config.dataset.num_scenes = 10
    config.camera.resolution = (640, 480)
    config.camera.samples_per_scene = 1
    return config


@pytest.fixture
def mock_job_spec(mock_gen_config, tmp_path):
    """Returns a valid JobSpec with consistent hashes."""
    # Create dummy paths
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    paths = JobPaths(
        output_dir=output_dir,
        logs_dir=output_dir / "logs",
        assets_dir=output_dir / "assets",
    )

    config_hash = hashlib.sha256(mock_gen_config.model_dump_json().encode()).hexdigest()

    # Create the spec
    spec = JobSpec(
        job_id="pending",  # Placeholder
        paths=paths,
        global_seed=42,
        scene_config=mock_gen_config,
        env_hash="dummy_env_hash",
        blender_version="4.2.0",
        assets_hash="dummy_assets_hash",
        config_hash=config_hash,
        shard_index=0,
    )

    # Calculate real ID
    final_id = calculate_job_id(spec)
    return spec.model_copy(update={"job_id": final_id})
