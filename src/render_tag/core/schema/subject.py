from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator, RootModel

class TagSubjectConfig(BaseModel):
    """Configuration for a collection of flying tags."""
    type: Literal["TAGS"] = "TAGS"
    tag_families: list[str] = Field(default_factory=lambda: ["tag36h11"])
    size_meters: PositiveFloat = 0.1
    tags_per_scene: PositiveInt = 10
    
    model_config = ConfigDict(use_enum_values=True)

class BoardSubjectConfig(BaseModel):
    """Configuration for a single calibration board."""
    type: Literal["BOARD"] = "BOARD"
    rows: PositiveInt
    cols: PositiveInt
    marker_size: PositiveFloat
    dictionary: str = "tag36h11"
    
    # AprilGrid specific
    spacing_ratio: PositiveFloat | None = None
    
    # ChArUco specific
    square_size: PositiveFloat | None = None

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def validate_board_constraints(self) -> "BoardSubjectConfig":
        if self.square_size is not None:
            if self.marker_size >= self.square_size:
                raise ValueError("marker_size must be smaller than square_size")
        return self

# Discriminated Union for polymorphism
class SubjectConfig(RootModel):
    root: Annotated[
        Union[TagSubjectConfig, BoardSubjectConfig],
        Field(discriminator="type")
    ]
