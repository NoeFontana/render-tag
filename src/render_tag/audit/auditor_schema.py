"""
Schemas for Dataset Auditing.
"""

from pydantic import BaseModel, Field


class DistributionStats(BaseModel):
    """Statistical distribution summary."""

    min: float
    max: float
    mean: float
    std: float
    median: float


class GeometricAudit(BaseModel):
    """Audit results for geometric coverage."""

    distance: DistributionStats
    incidence_angle: DistributionStats
    tag_count: int
    image_count: int


class EnvironmentalAudit(BaseModel):
    """Audit results for environmental variance."""

    lighting_intensity: DistributionStats
    contrast: DistributionStats | None = None


class IntegrityAudit(BaseModel):
    """Audit results for data integrity."""

    orphaned_tags: int = 0
    impossible_poses: int = 0
    corrupted_frames: int = 0


class AuditReport(BaseModel):
    """Complete audit report for a dataset."""

    dataset_name: str
    timestamp: str
    geometric: GeometricAudit
    environmental: EnvironmentalAudit
    integrity: IntegrityAudit
    score: float = 0.0


class GateRule(BaseModel):
    """A single rule for a quality gate."""

    metric: str
    min: float | None = None
    max: float | None = None
    critical: bool = True
    warning_msg: str | None = None
    error_msg: str | None = None


class QualityGateConfig(BaseModel):
    """Configuration for quality gates."""

    rules: list[GateRule] = Field(default_factory=list)


class AuditResult(BaseModel):
    """Final result of an audit run, including gates."""

    report: AuditReport
    gate_passed: bool = True
    gate_failures: list[str] = Field(default_factory=list)
