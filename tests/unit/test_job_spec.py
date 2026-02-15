from pathlib import Path

import pytest
from pydantic import ValidationError

from render_tag.core.config import GenConfig
from render_tag.core.schema.job import JobInfrastructure, JobPaths, JobSpec, calculate_job_id


def test_job_spec_immutability():
    config = GenConfig()
    paths = JobPaths(
        output_dir=Path("/tmp/out"),
        logs_dir=Path("/tmp/out/logs"),
        assets_dir=Path("/tmp/assets"),
    )
    spec = JobSpec(
        job_id="job-123",
        paths=paths,
        infrastructure=JobInfrastructure(),
        global_seed=42,
        scene_config=config,
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
    )

    # Try to modify a field
    with pytest.raises(ValidationError):
        spec.global_seed = 43


def test_job_id_determinism():
    config = GenConfig()
    paths = JobPaths(
        output_dir=Path("/tmp/out"),
        logs_dir=Path("/tmp/out/logs"),
        assets_dir=Path("/tmp/assets"),
    )

    from datetime import datetime

    fixed_time = datetime(2025, 1, 1)

    spec1 = JobSpec(
        job_id="job-123",
        created_at=fixed_time,
        paths=paths,
        infrastructure=JobInfrastructure(),
        global_seed=42,
        scene_config=config,
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
    )
    spec2 = JobSpec(
        job_id="job-123",
        created_at=fixed_time,
        paths=paths,
        infrastructure=JobInfrastructure(),
        global_seed=42,
        scene_config=config,
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
    )
    assert calculate_job_id(spec1) == calculate_job_id(spec2)


def test_job_id_changes_with_content():
    config = GenConfig()
    paths = JobPaths(
        output_dir=Path("/tmp/out"),
        logs_dir=Path("/tmp/out/logs"),
        assets_dir=Path("/tmp/assets"),
    )

    spec1 = JobSpec(
        job_id="job-123",  # job_id itself usually doesn't change the hash if we hash content?
        # But calculate_job_id hashes the spec json.
        # If we change seed, hash should change.
        paths=paths,
        infrastructure=JobInfrastructure(),
        global_seed=42,
        scene_config=config,
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
    )
    spec2 = JobSpec(
        job_id="job-123",
        paths=paths,
        infrastructure=JobInfrastructure(),
        global_seed=43,  # Changed seed
        scene_config=config,
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
    )
    assert calculate_job_id(spec1) != calculate_job_id(spec2)
