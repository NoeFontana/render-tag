
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, PositiveFloat, model_validator

class BoardType(str, Enum):
    APRILGRID = "aprilgrid"
    CHARUCO = "charuco"

class BoardConfig(BaseModel):
    """Configuration for a calibration board."""
    type: BoardType
    rows: PositiveInt
    cols: PositiveInt
    
    # Common parameters
    marker_size: PositiveFloat
    dictionary: str = "tag36h11"
    
    # AprilGrid specific
    spacing_ratio: Optional[PositiveFloat] = None
    
    # ChArUco specific
    square_size: Optional[PositiveFloat] = None

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def validate_board_constraints(self) -> "BoardConfig":
        if self.type == BoardType.CHARUCO:
            if self.square_size is None:
                raise ValueError("square_size is required for ChArUco")
            if self.marker_size >= self.square_size:
                raise ValueError("marker_size must be smaller than square_size")
        elif self.type == BoardType.APRILGRID:
            if self.spacing_ratio is None:
                raise ValueError("spacing_ratio is required for AprilGrid")
        return self
