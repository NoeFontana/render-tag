from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    RootModel,
    model_validator,
)


class TagSubjectConfig(BaseModel):
    """Configuration for a collection of flying tags.

    Attributes:
        type: Discriminator for polymorphic schema.
        tag_families: List of tag families to sample from.
        size_meters: Edge length of the markers in meters.
        tags_per_scene: Number of markers to generate per scene.
    """

    type: Literal["TAGS"] = "TAGS"
    tag_families: list[str] = Field(default_factory=lambda: ["tag36h11"])
    size_meters: PositiveFloat = 0.1
    tags_per_scene: PositiveInt = 10
    tag_spacing_bits: float = Field(default=2.0, description="Spacing between tags in bits")

    model_config = ConfigDict(use_enum_values=True)


class BoardSubjectConfig(BaseModel):
    """Configuration for a single calibration board.

    Attributes:
        type: Discriminator for polymorphic schema.
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        marker_size: Edge length of the markers in meters.
        dictionary: Tag family used for markers.
        spacing_ratio: Ratio of marker size to spacing (AprilGrid only).
        square_size: Total edge length of a grid cell (ChArUco only).
    """

    type: Literal["BOARD"] = "BOARD"
    rows: PositiveInt
    cols: PositiveInt
    marker_size: PositiveFloat
    dictionary: str = "tag36h11"

    # AprilGrid specific
    spacing_ratio: PositiveFloat | None = None

    # ChArUco specific
    square_size: PositiveFloat | None = None

    # Optional explicit ID mapping
    ids: list[int] | None = None

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def validate_board_constraints(self) -> BoardSubjectConfig:
        """Validate that square_size is greater than marker_size for ChArUco.

        Returns:
            The validated BoardSubjectConfig instance.

        Raises:
            ValueError: If constraints are violated.
        """
        if self.square_size is not None and self.marker_size >= self.square_size:
            raise ValueError("marker_size must be smaller than square_size")
        return self


# Discriminated Union for polymorphism
class SubjectConfig(RootModel):
    """Root model for polymorphic subjects."""

    root: Annotated[TagSubjectConfig | BoardSubjectConfig, Field(discriminator="type")]
