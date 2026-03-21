
import pytest
from typer.testing import CliRunner
from render_tag.cli.main import app
from unittest.mock import patch, MagicMock
from render_tag.orchestration.result import OrchestrationResult, ExecutionTimings, JobMetadata

runner = CliRunner()

@patch("render_tag.cli.stages.execution_stage.orchestrate")
@patch("render_tag.cli.stages.config_stage.ConfigLoadingStage.execute")
@patch("render_tag.cli.stages.prep_stage.PreparationStage.execute")
def test_cli_generate_reports_results(mock_prep, mock_config, mock_orchestrate, tmp_path):
    """Verify that 'render-tag generate' calls orchestrate and reports results."""
    # Mock result
    mock_result = OrchestrationResult(
        success_count=5,
        failed_count=0,
        timings=ExecutionTimings(total_duration_s=10.0),
        metadata=JobMetadata(job_spec_hash="h1", env_state_hash="h2")
    )
    mock_orchestrate.return_value = mock_result
    
    # Run CLI
    result = runner.invoke(app, ["generate", "--config", "dummy.yaml", "--workers", "2", "--output", str(tmp_path)])
    
    assert result.exit_code == 0
    assert "Orchestration Summary" in result.stdout
    assert "Success Count" in result.stdout
    assert "5" in result.stdout

@patch("render_tag.cli.stages.execution_stage.orchestrate")
@patch("render_tag.cli.stages.config_stage.ConfigLoadingStage.execute")
@patch("render_tag.cli.stages.prep_stage.PreparationStage.execute")
def test_cli_generate_fails_on_errors(mock_prep, mock_config, mock_orchestrate, tmp_path):
    """Verify that CLI exits with code 1 if orchestration has failures."""
    mock_result = OrchestrationResult(
        success_count=4,
        failed_count=1,
        timings=ExecutionTimings(total_duration_s=10.0),
        metadata=JobMetadata(job_spec_hash="h1", env_state_hash="h2")
    )
    mock_orchestrate.return_value = mock_result
    
    result = runner.invoke(app, ["generate", "--config", "dummy.yaml", "--workers", "2", "--output", str(tmp_path)])
    
    assert result.exit_code == 1
    assert "Parallel generation failed with errors" in result.stdout
