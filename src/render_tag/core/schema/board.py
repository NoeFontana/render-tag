from enum import Enum

from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt, model_validator


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
    spacing_ratio: PositiveFloat | None = None

    # ChArUco specific
    square_size: PositiveFloat | None = None

    # Optional explicit ID mapping
    ids: list[int] | None = None

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def validate_board_constraints(self) -> "BoardConfig":
        """Validate type-specific constraints for calibration boards.

        Returns:
            The validated BoardConfig instance.

        Raises:
            ValueError: If square_size is missing for ChArUco, spacing_ratio is
                missing for AprilGrid, or if marker_size is not smaller than
                square_size for ChArUco.
        """
        if self.type == BoardType.CHARUCO:
            if self.square_size is None:
                raise ValueError("square_size is required for ChArUco")
            if self.marker_size >= self.square_size:
                raise ValueError("marker_size must be smaller than square_size")
        elif self.type == BoardType.APRILGRID:
            if self.spacing_ratio is None:
                raise ValueError("spacing_ratio is required for AprilGrid")
        return self
