from unittest.mock import MagicMock

import pytest

from render_tag.cli.reporters import JsonFileReporter, RichTerminalReporter
from render_tag.orchestration.result import ExecutionTimings, JobMetadata, OrchestrationResult


@pytest.fixture
def sample_result():
    return OrchestrationResult(
        success_count=10,
        failed_count=0,
        timings=ExecutionTimings(total_duration_s=120.0),
        metadata=JobMetadata(job_spec_hash="h1", env_state_hash="h2"),
    )


def test_rich_terminal_reporter_calls_rich(sample_result):
    """Verify that RichTerminalReporter uses rich console to print results."""
    mock_console = MagicMock()
    reporter = RichTerminalReporter(console=mock_console)

    reporter.report(sample_result)

    # Check if print or similar was called
    assert mock_console.print.called


def test_json_file_reporter_writes_to_file(sample_result, tmp_path):
    """Verify that JsonFileReporter writes the result to a JSON file."""
    output_file = tmp_path / "result.json"
    reporter = JsonFileReporter(output_path=output_file)

    reporter.report(sample_result)

    assert output_file.exists()
    import json

    with open(output_file) as f:
        data = json.load(f)
        assert data["success_count"] == 10


def test_rich_terminal_reporter_complex(sample_result):
    """Verify RichTerminalReporter with errors and metrics."""
    from render_tag.orchestration.result import ErrorRecord, WorkerMetrics

    sample_result.worker_metrics = WorkerMetrics(worker_id="w1", max_ram_mb=100, max_vram_mb=200)
    sample_result.errors = [ErrorRecord(scene_id=1, error_message="fail")] * 15

    mock_console = MagicMock()
    reporter = RichTerminalReporter(console=mock_console)
    reporter.report(sample_result)

    # Check that it printed "and 5 more errors" or similar
    # In my implementation it's: f"... and {len(result.errors) - 10} more errors."
    calls = [
        call[0][0] for call in mock_console.print.call_args_list if isinstance(call[0][0], str)
    ]
    assert any("5 more errors" in c for c in calls)
