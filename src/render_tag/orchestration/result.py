
from typing import Any
from pydantic import BaseModel, Field

class WorkerMetrics(BaseModel):
    """Worker-reported performance and resource utilization metrics."""
    worker_id: str
    max_ram_mb: float = 0.0
    max_vram_mb: float = 0.0

class ErrorRecord(BaseModel):
    """Details of a failed scene rendering."""
    scene_id: int
    error_message: str
    traceback: str | None = None

class ExecutionTimings(BaseModel):
    """Duration of various orchestration stages in seconds."""
    total_duration_s: float
    stages: dict[str, float] = Field(default_factory=dict)

class JobMetadata(BaseModel):
    """Provenance and state tracking for the orchestration job."""
    job_spec_hash: str
    env_state_hash: str

class OrchestrationResult(BaseModel):
    """Standardized DTO for the results of an orchestration execution."""
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    worker_metrics: WorkerMetrics | None = None
    errors: list[ErrorRecord] = Field(default_factory=list)
    timings: ExecutionTimings
    metadata: JobMetadata
