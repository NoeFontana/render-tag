from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    RootModel,
    field_validator,
    model_validator,
)

from render_tag.core.constants import SUPPORTED_OPENCV_TAG_FAMILIES


class TagSubjectConfig(BaseModel):
    """Configuration for a collection of flying tags.

    Attributes:
        type: Discriminator for polymorphic schema.
        tag_families: List of tag families to sample from.
        size_mm: Edge length of the markers in millimeters.
        tags_per_scene: Number of markers to generate per scene.
    """

    type: Literal["TAGS"] = "TAGS"
    tag_families: list[str] = Field(default_factory=lambda: ["tag36h11"])
    size_mm: PositiveFloat = 100.0
    tags_per_scene: int | tuple[int, int] = Field(
        default=10, description="Number of markers to generate per scene (or [min, max] range)."
    )
    tag_spacing_bits: float = Field(default=2.0, description="Spacing between tags in bits")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("tag_families")
    @classmethod
    def validate_tag_families(cls, v: list[str]) -> list[str]:
        """Reject tag families this environment cannot render."""
        unsupported = [family for family in v if family not in SUPPORTED_OPENCV_TAG_FAMILIES]
        if unsupported:
            raise ValueError(f"Unsupported tag families: {unsupported}")
        return v

    @model_validator(mode="before")
    @classmethod
    def migrate_units(cls, data: Any) -> Any:
        """Migrate size_meters to size_mm."""
        if isinstance(data, dict) and "size_meters" in data:
            data["size_mm"] = data.pop("size_meters") * 1000.0
        return data


class BoardSubjectConfig(BaseModel):
    """Configuration for a single calibration board.

    Attributes:
        type: Discriminator for polymorphic schema.
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        marker_size_mm: Edge length of the markers in millimeters.
        dictionary: Tag family used for markers.
        spacing_ratio: Ratio of marker size to spacing (AprilGrid only).
        square_size_mm: Total edge length of a grid cell (ChArUco only).
    """

    type: Literal["BOARD"] = "BOARD"
    rows: PositiveInt
    cols: PositiveInt
    marker_size_mm: PositiveFloat
    dictionary: str = "tag36h11"

    # AprilGrid specific
    spacing_ratio: PositiveFloat | None = None

    # ChArUco specific
    square_size_mm: PositiveFloat | None = None

    # Optional quiet zone (white border) around the grid
    quiet_zone_mm: float = Field(default=0.0, ge=0.0)

    # Optional explicit ID mapping
    ids: list[int] | None = None

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("dictionary")
    @classmethod
    def validate_dictionary(cls, v: str) -> str:
        """Reject board dictionaries this environment cannot render."""
        if v not in SUPPORTED_OPENCV_TAG_FAMILIES:
            raise ValueError(f"Unsupported board dictionary: {v}")
        return v

    @model_validator(mode="before")
    @classmethod
    def migrate_units(cls, data: Any) -> Any:
        """Migrate meters to millimeters."""
        if not isinstance(data, dict):
            return data

        if "marker_size" in data:
            data["marker_size_mm"] = data.pop("marker_size") * 1000.0
        if "square_size" in data:
            data["square_size_mm"] = data.pop("square_size") * 1000.0
        return data

    @model_validator(mode="after")
    def validate_board_constraints(self) -> BoardSubjectConfig:
        """Validate that square_size_mm is greater than marker_size_mm for ChArUco."""
        if self.square_size_mm is not None and self.marker_size_mm >= self.square_size_mm:
            raise ValueError("marker_size_mm must be smaller than square_size_mm")
        return self


# Discriminated Union for polymorphism
class SubjectConfig(RootModel):
    """Root model for polymorphic subjects."""

    root: Annotated[TagSubjectConfig | BoardSubjectConfig, Field(discriminator="type")]
