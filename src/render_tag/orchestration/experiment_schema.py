"""
Experiment Schema for render-tag.

Defines the structure for Controlled Experiments (sweeps, locks) to enable
reproducible science.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from render_tag.core.config import GenConfig


class SweepType(str, Enum):
    LINEAR = "linear"
    CATEGORICAL = "categorical"


class CameraStandard(str, Enum):
    """Standardized camera profiles for reproduction."""

    FHD_GLOBAL_PERCEPTION = "FHD_Global_Perception"  # 1920x1080, 70deg HFOV, Global Shutter
    VGA_LEGACY = "VGA_Legacy"  # 640x480, 60deg HFOV


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
    overrides: dict[str, Any] = Field(
        default_factory=dict, description="Overrides for this sub-experiment"
    )


class CampaignAxis(BaseModel):
    """A single axis in a campaign matrix (Cartesian product factor)."""

    parameter: str = Field(
        description=(
            "Dot-notation path into the config dict, e.g. 'camera.resolution'. "
            "Numeric segments index into lists."
        )
    )
    values: list[Any] = Field(min_length=1, description="Values to sweep across this axis (>= 1)")


class CampaignMatrix(BaseModel):
    """A benchmark-family x axes template that expands Cartesian-style.

    ``base`` is a ``SubExperiment`` template (config path + any fixed
    overrides). Each axis contributes one dotted parameter and its values;
    the final variant count is ``prod(len(axis.values))``. Axis values are
    written into ``overrides`` along with any per-base-experiment overrides,
    and the variant name is ``{base.name}__{axis1_slug}_{axis2_slug}...``.
    """

    base: SubExperiment = Field(description="Template sub-experiment (config + fixed overrides)")
    axes: list[CampaignAxis] = Field(min_length=1, description="Axes to expand (>= 1)")


class Campaign(BaseModel):
    """A master configuration for a multi-experiment campaign."""

    output_dir: str = Field(description="Base output directory for the campaign")
    experiments: list[SubExperiment] = Field(
        default_factory=list,
        description="Explicitly enumerated sub-experiments",
    )
    matrices: list[CampaignMatrix] = Field(
        default_factory=list,
        description="Benchmark x axes templates; expand Cartesian-style at load time",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Global metadata for the campaign"
    )

    @model_validator(mode="after")
    def _non_empty(self) -> "Campaign":
        if not self.experiments and not self.matrices:
            raise ValueError("Campaign must define at least one of `experiments:` or `matrices:`")
        return self
