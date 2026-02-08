import pytest
from pydantic import ValidationError
from render_tag.schema.job import JobSpec, calculate_job_id

def test_job_spec_immutability():
    spec = JobSpec(
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
        config_hash="def",
        seed=42,
        shard_index=0,
        shard_size=10
    )
    with pytest.raises(ValidationError):
        spec.seed = 43

def test_job_id_determinism():
    spec1 = JobSpec(
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
        config_hash="def",
        seed=42,
        shard_index=0,
        shard_size=10
    )
    spec2 = JobSpec(
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
        config_hash="def",
        seed=42,
        shard_index=0,
        shard_size=10
    )
    assert calculate_job_id(spec1) == calculate_job_id(spec2)

def test_job_id_changes_with_content():
    spec1 = JobSpec(
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
        config_hash="def",
        seed=42,
        shard_index=0,
        shard_size=10
    )
    spec2 = JobSpec(
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
        config_hash="def",
        seed=43,  # Changed seed
        shard_index=0,
        shard_size=10
    )
    assert calculate_job_id(spec1) != calculate_job_id(spec2)
