
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

def test_orchestration_result_serialization():
    """Verify that OrchestrationResult can be serialized to JSON and back."""
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
    json_data = result.model_dump_json()
    new_result = OrchestrationResult.model_validate_json(json_data)
    assert new_result.success_count == 10
    assert new_result.timings.total_duration_s == 120.5
    assert new_result.metadata.job_spec_hash == "abc123hash"

def test_orchestration_result_defaults():
    """Verify default values for OrchestrationResult fields."""
    data = {
        "timings": {"total_duration_s": 10.0},
        "metadata": {"job_spec_hash": "h1", "env_state_hash": "h2"}
    }
    result = OrchestrationResult(**data)
    assert result.success_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 0
    assert result.errors == []
    assert result.worker_metrics is None
