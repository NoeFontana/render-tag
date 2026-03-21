
import pytest
import os
from pathlib import Path
from render_tag.orchestration.orchestrator import orchestrate, OrchestratorConfig
from render_tag.core.schema.job import JobSpec
from unittest.mock import MagicMock, patch
from render_tag.core.config import GenConfig

def test_orchestrate_mock_integration(tmp_path):
    """Run a small orchestration job with mock workers to verify pure logic and DTO."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    # Mock JobSpec
    job_spec = MagicMock()
    job_spec.scene_config = GenConfig()
    job_spec.paths.output_dir = output_dir
    job_spec.global_seed = 42
    job_spec.shard_size = 2
    job_spec.infrastructure.max_memory_mb = 1024
    job_spec.get_total_shards.return_value = 1
    job_spec.model_dump_json.return_value = '{"test": true}'
    
    # Force mock mode
    os.environ["RENDER_TAG_FORCE_MOCK"] = "1"
    
    # Progress callback tracker
    progress_updates = []
    def progress_cb(inc, total):
        progress_updates.append((inc, total))
        
    result = orchestrate(
        job_spec,
        workers=2,
        batch_size=1,
        progress_cb=progress_cb
    )
    
    assert result.success_count + result.failed_count == 2
    assert result.timings.total_duration_s > 0
    assert len(progress_updates) > 0
    assert result.metadata.job_spec_hash is not None

def test_orchestrate_all_complete(tmp_path):
    """Verify orchestrate behavior when all shards are already complete."""
    job_spec = MagicMock()
    job_spec.shard_size = 10
    job_spec.model_dump_json.return_value = '{"test": true}'
    
    with patch("render_tag.orchestration.orchestrator._prepare_batches") as mock_prep:
        mock_prep.return_value = (None, 0, 1)
        
        result = orchestrate(job_spec)
        assert result.success_count == 0
        assert result.skipped_count == 10
        assert result.timings.total_duration_s >= 0
