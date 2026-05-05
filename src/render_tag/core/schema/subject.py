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


class OccluderConfig(BaseModel):
    """Half-plane shadow plates that cast realistic edge/corner/slit shadows on the tag.

    A plate is a horizontal rectangle floating at height ``h`` above the tag plane.
    Its edge/corner is anchored along the sun ray so that the projected umbra
    intersects the tag cluster. Four patterns are supported:

    - ``half``: 1 large plate, single straight shadow edge (half-plane).
    - ``corner``: 1 large plate anchored at its corner, quadrant shadow.
    - ``bar``: 1 narrow plate centered on anchor, shadow strip.
    - ``slit``: 2 large plates with a gap, narrow lit strip between two shadows.
    """

    enabled: bool = Field(default=True)
    patterns: list[Literal["half", "corner", "bar", "slit"]] = Field(
        default_factory=lambda: ["half", "corner", "bar", "slit"],
        min_length=1,
    )
    plate_size_m: PositiveFloat = Field(
        default=0.5, description="Size of 'large' plates used in half/corner/slit."
    )
    plate_thickness_m: PositiveFloat = Field(default=0.005)
    height_min_m: PositiveFloat = Field(default=0.05)
    height_max_m: PositiveFloat = Field(default=0.20)

    # Offsets and widths are relative to the tag cluster radius R
    # (e.g. edge_offset_max_r=1.0 means the shadow edge can be anywhere on the tag)
    edge_offset_max_r: float = Field(
        default=1.0, ge=0.0, description="Max edge shift relative to tag radius."
    )
    bar_width_min_r: PositiveFloat = Field(
        default=0.1, description="Min bar width relative to tag radius."
    )
    bar_width_max_r: PositiveFloat = Field(
        default=0.5, description="Max bar width relative to tag radius."
    )
    slit_width_min_r: PositiveFloat = Field(
        default=0.1, description="Min slit width relative to tag radius."
    )
    slit_width_max_r: PositiveFloat = Field(
        default=0.5, description="Max slit width relative to tag radius."
    )

    albedo: float = Field(default=0.05, ge=0.0, le=1.0)
    roughness: float = Field(default=0.9, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_ranges(self) -> OccluderConfig:
        if self.height_max_m < self.height_min_m:
            raise ValueError("height_max_m must be >= height_min_m")
        if self.bar_width_max_r < self.bar_width_min_r:
            raise ValueError("bar_width_max_r must be >= bar_width_min_r")
        if self.slit_width_max_r < self.slit_width_min_r:
            raise ValueError("slit_width_max_r must be >= slit_width_min_r")
        return self
