"""Unified Metadata Schema for render-tag."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from render_tag.core.config import EvaluationScope


class ProvenanceMetadata(BaseModel):
    """Provenance information for the dataset."""

    git_commit: str = Field(default="unknown")
    render_tag_version: str = Field(default="unknown")
    render_tag_env_hash: str = Field(default="unknown")
    blenderproc_version: str = Field(default="unknown")
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    command: str = Field(default="unknown")


class CameraIntrinsicsMetadata(BaseModel):
    """Camera intrinsics for the dataset."""

    focal_length_px: list[float] = Field(description="[fx, fy] in pixels")
    principal_point: list[float] = Field(description="[cx, cy] in pixels")
    resolution: list[int] = Field(description="[width, height] in pixels")


class TagSpecificationMetadata(BaseModel):
    """Tag physical specification."""

    tag_family: str = Field(description="Name of the tag family")
    tag_size_m: float = Field(description="Tag size in meters")


class ExperimentMetadata(BaseModel):
    """Optional metadata for experiments/sweeps."""

    name: str | None = None
    variant_id: str | None = None
    description: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)
    seed_info: dict[str, int] = Field(default_factory=dict)


class DatasetMetadata(BaseModel):
    """Consolidated metadata for a generated dataset."""

    model_config = ConfigDict(extra="forbid")

    provenance: ProvenanceMetadata = Field(default_factory=ProvenanceMetadata)
    camera_intrinsics: CameraIntrinsicsMetadata
    tag_specification: TagSpecificationMetadata
    pose_convention: Literal["xyzw"] = Field(
        default="xyzw", description="Quaternion convention (Scalar Last)"
    )
    evaluation_scopes: list[EvaluationScope] = Field(
        default_factory=lambda: [EvaluationScope.DETECTION]
    )
    experiment: ExperimentMetadata | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
