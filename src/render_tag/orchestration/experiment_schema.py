"""
Experiment Schema for render-tag.

Defines the structure for Controlled Experiments (sweeps, locks) to enable
reproducible science.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from render_tag.core.config import GenConfig


class SweepType(str, Enum):
    LINEAR = "linear"
    CATEGORICAL = "categorical"


class Sweep(BaseModel):
    """A definition of a single parameter sweep."""

    parameter: str = Field(
        description="Dot-notation path to the config parameter (e.g. 'camera.min_distance')"
    )
    type: SweepType = Field(description="Type of sweep: linear or categorical")

    # For Categorical
    values: list[Any] | None = Field(
        default=None, description="List of values for categorical sweep"
    )

    # For Linear
    min: float | None = Field(default=None, description="Start value")
    max: float | None = Field(default=None, description="End value")
    step: float | None = Field(default=None, description="Step size")
    steps: int | None = Field(
        default=None, description="Number of steps (alternative to step size)"
    )

    @model_validator(mode="after")
    def validate_sweep(self) -> "Sweep":
        if self.type == SweepType.CATEGORICAL:
            if not self.values:
                raise ValueError("Categorical sweep must provide 'values'")
        elif self.type == SweepType.LINEAR:
            if self.min is None or self.max is None:
                raise ValueError("Linear sweep must provide 'min' and 'max'")
            if self.step is None and self.steps is None:
                raise ValueError("Linear sweep must provide 'step' or 'steps'")
        return self


class Experiment(BaseModel):
    """Root configuration for an Experiment."""

    name: str = Field(description="Unique name for this experiment")
    description: str = Field(default="", description="Description of the hypothesis/goal")

    base_config: GenConfig = Field(description="The invariant base configuration")

    sweeps: list[Sweep] = Field(default_factory=list, description="List of variables to sweep")

    # Lock configuration
    lock_layout: bool = Field(
        default=True, description="If True, layout_seed is constant across variants"
    )
    lock_lighting: bool = Field(
        default=True, description="If True, lighting_seed is constant across variants"
    )
    lock_camera: bool = Field(
        default=False,
        description="If True, camera_seed is constant (usually False for dist/angle sweeps)",
    )


class ExperimentVariant(BaseModel):
    """A single resolved variant from an experiment."""

    experiment_name: str
    variant_id: str
    description: str

    config: GenConfig = Field(description="The fully resolved configuration for this variant")
    overrides: dict[str, Any] = Field(description="The parameters that were modified from base")


class SubExperiment(BaseModel):
    """A single experiment within a larger campaign."""
    name: str
    config_path: str = Field(alias="config", description="Path to the preset config file")
    overrides: dict[str, Any] = Field(default_factory=dict, description="Overrides for this sub-experiment")


class Campaign(BaseModel):
    """A master configuration for a multi-experiment campaign."""
    output_dir: str = Field(description="Base output directory for the campaign")
    experiments: list[SubExperiment] = Field(description="List of sub-experiments to run")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Global metadata for the campaign")


class CameraIntrinsicsManifest(BaseModel):
    """Camera intrinsics for the dataset manifest."""
    focal_length_px: list[float] = Field(description="[fx, fy] in pixels")
    principal_point: list[float] = Field(description="[cx, cy] in pixels")
    resolution: list[int] = Field(description="[width, height] in pixels")


class TagSpecificationManifest(BaseModel):
    """Tag physical specification for the dataset manifest."""
    tag_family: str = Field(description="Name of the tag family (e.g. tag36h11)")
    tag_size_mm: int = Field(description="Tag size in millimeters (integer)")


class SweepDefinitionManifest(BaseModel):
    """Optional definition of the parameter sweep performed."""
    variable_name: str = Field(description="Name of the swept variable")
    range: list[float] = Field(description="Range of values [start, end]")


class DatasetManifest(BaseModel):
    """Strict contract for dataset_info.json metadata."""
    camera_intrinsics: CameraIntrinsicsManifest
    tag_specification: TagSpecificationManifest
    pose_convention: Literal["wxyz"] = Field(
        default="wxyz",
        description="Quaternion convention (Scalar First)"
    )
    sweep_definition: SweepDefinitionManifest | None = Field(
        default=None,
        description="Optional metadata about the sweep"
    )
