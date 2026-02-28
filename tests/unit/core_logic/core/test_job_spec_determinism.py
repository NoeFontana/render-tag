from pathlib import Path

from render_tag.core.config import GenConfig
from render_tag.core.schema.job import JobPaths, JobSpec


def test_job_spec_shard_mapping_is_deterministic():
    """Verify that a JobSpec returns consistent scene indices for a given shard."""
    config = GenConfig()
    config.dataset.num_scenes = 1000

    paths = JobPaths(output_dir=Path("output"), logs_dir=Path("logs"), assets_dir=Path("assets"))

    spec = JobSpec(
        job_id="test_job",
        paths=paths,
        global_seed=42,
        scene_config=config,
        env_hash="abc",
        blender_version="4.2.1",
        shard_index=5,  # Shard 5
    )

    # We want to define a property or method to get scenes for this shard
    # For 1000 scenes and let's say 100 scenes per shard (determined by some logic)
    # Shard 5 should always give the same range.

    # Proposed API: spec.get_scene_indices()
    indices1 = spec.get_scene_indices(scenes_per_shard=100)
    indices2 = spec.get_scene_indices(scenes_per_shard=100)

    assert indices1 == indices2
    assert indices1 == list(range(500, 600))


def test_job_spec_total_shards():
    """Verify calculation of total shards needed."""
    config = GenConfig()
    config.dataset.num_scenes = 1050

    paths = JobPaths(output_dir=Path("output"), logs_dir=Path("logs"), assets_dir=Path("assets"))

    spec = JobSpec(
        job_id="test_job",
        paths=paths,
        global_seed=42,
        scene_config=config,
        env_hash="abc",
        blender_version="4.2.1",
    )

    # Proposed API: spec.get_total_shards(scenes_per_shard=100)
    assert spec.get_total_shards(scenes_per_shard=100) == 11
