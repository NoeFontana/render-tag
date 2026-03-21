
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from render_tag.orchestration.orchestrator import orchestrate
from render_tag.orchestration.result import OrchestrationResult
from render_tag.core.schema.job import JobSpec

@pytest.fixture
def mock_job_spec():
    job = MagicMock()
    job.paths.output_dir = Path("/tmp/test_output")
    job.scene_config.renderer.mode = "workbench"
    job.global_seed = 42
    job.shard_size = 10
    job.infrastructure.max_memory_mb = 1024
    job.get_total_shards.return_value = 2
    job.model_dump_json.return_value = '{"test": true}'
    return job

@patch("render_tag.orchestration.orchestrator._prepare_batches")
@patch("render_tag.orchestration.orchestrator.UnifiedWorkerOrchestrator")
@patch("render_tag.orchestration.orchestrator._run_orchestration_loop")
def test_orchestrate_returns_result(mock_run, mock_orchestrator, mock_prepare, mock_job_spec):
    """Verify that orchestrate() returns an OrchestrationResult object."""
    mock_prepare.return_value = ([Path("shard_0.json")], 5, 2)
    mock_run.return_value = [] # No failures (empty list of ErrorRecord)
    
    result = orchestrate(mock_job_spec, workers=1)
    
    assert isinstance(result, OrchestrationResult)
    assert result.success_count >= 0
    assert result.failed_count == 0

@patch("render_tag.orchestration.orchestrator._prepare_batches")
def test_orchestrate_no_typer_dependency(mock_prepare, mock_job_spec):
    """Verify that orchestrate() does not raise typer.Exit."""
    mock_prepare.return_value = (None, 5, 2) # All complete
    
    # This should NOT raise typer.Exit
    try:
        result = orchestrate(mock_job_spec)
        assert isinstance(result, OrchestrationResult)
    except Exception as e:
        if "typer" in str(type(e)):
             pytest.fail(f"orchestrate() still depends on typer: {e}")
        raise e
