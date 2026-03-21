
import pytest
from pydantic import ValidationError
from render_tag.orchestration.result import OrchestrationResult, WorkerMetrics, ErrorRecord

def test_orchestration_result_basic_validation():
    """Verify that OrchestrationResult can be instantiated with valid data."""
    data = {
        "success_count": 10,
        "failed_count": 2,
        "skipped_count": 1,
        "worker_metrics": {
            "worker_id": "worker-1",
            "max_ram_mb": 1024.5,
            "max_vram_mb": 512.0
        },
        "errors": [
            {
                "scene_id": 5,
                "error_message": "Resource limit exceeded",
                "traceback": "Traceback..."
            }
        ],
        "timings": {
            "total_duration_s": 120.5,
            "stages": {"init": 10.0, "render": 110.5}
        },
        "metadata": {
            "job_spec_hash": "abc123hash",
            "env_state_hash": "xyz789hash"
        }
    }
    result = OrchestrationResult(**data)
    assert result.success_count == 10
    assert result.failed_count == 2
    assert result.worker_metrics.worker_id == "worker-1"

def test_orchestration_result_missing_fields():
    """Verify that missing required fields raise ValidationError."""
    with pytest.raises(ValidationError):
        OrchestrationResult(success_count=10) # Missing failed_count, timings, etc.

def test_worker_metrics_validation():
    """Verify WorkerMetrics field validation."""
    with pytest.raises(ValidationError):
        WorkerMetrics(worker_id="w1", max_ram_mb="not-a-float")
