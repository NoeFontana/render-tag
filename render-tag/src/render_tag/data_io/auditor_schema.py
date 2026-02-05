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
