from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

from render_tag.core.constants import SUPPORTED_OPENCV_TAG_FAMILIES


class BoardType(str, Enum):
    APRILGRID = "aprilgrid"
    CHARUCO = "charuco"


class BoardConfig(BaseModel):
    """Configuration for a calibration board.

    Keypoint Contract (Top-Left, Clockwise):
        All exported keypoints_3d arrays follow OpenCV 4.6+ standard. For each
        marker, the four corners are serialized in this exact index order:

            Index 0: Top-Left     (-X, +Y in Blender local / min-X, min-Y in image)
            Index 1: Top-Right    (+X, +Y in Blender local / max-X, min-Y in image)
            Index 2: Bottom-Right (+X, -Y in Blender local / max-X, max-Y in image)
            Index 3: Bottom-Left  (-X, -Y in Blender local / min-X, max-Y in image)

        The winding is strictly Clockwise in image-space (Y-down, OpenCV convention),
        which corresponds to a positive Shoelace signed area. The pipeline MUST NOT
        re-sort or apply convex-hull algorithms to projected corners; index 0 always
        maps to Top-Left regardless of camera rotation.

        Calibration points (saddle points / AprilGrid intersections) are serialized
        left-to-right across each row, top-to-bottom (row 0 first), matching the
        iterator order of both the texture synthesizer and the layout generator.
    """

    type: BoardType
    rows: PositiveInt
    cols: PositiveInt

    # Common parameters
    marker_size: PositiveFloat
    dictionary: str = "tag36h11"

    # AprilGrid specific
    spacing_ratio: PositiveFloat | None = None
    kalibr_corner_ratio: PositiveFloat | None = None

    # ChArUco specific
    square_size: PositiveFloat | None = None

    # Optional quiet zone (white border) around the grid, in meters
    quiet_zone_m: float = Field(default=0.0, ge=0.0)

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
        if self.dictionary not in SUPPORTED_OPENCV_TAG_FAMILIES:
            raise ValueError(f"Unsupported board dictionary: {self.dictionary}")
        return self


class BoardDefinition(BaseModel):
    """Output descriptor shipped in BOARD DetectionRecords.

    Unlike BoardConfig (input configuration), this captures the resolved
    physical parameters needed to instantiate ``cv2.aruco.CharucoBoard`` or
    a Kalibr AprilGrid downstream without external config.
    """

    type: BoardType
    rows: PositiveInt
    cols: PositiveInt
    square_size_mm: float = Field(gt=0)
    marker_size_mm: float = Field(gt=0)
    dictionary: str
    total_keypoints: int = Field(ge=0)
    spacing_ratio: float | None = Field(default=None)
    kalibr_corner_ratio: float | None = Field(default=None)

    model_config = ConfigDict(use_enum_values=True, frozen=True)

    @model_validator(mode="after")
    def validate_aprilgrid_spacing(self) -> "BoardDefinition":
        """Validate that AprilGrid definitions include spacing_ratio."""
        if self.type == BoardType.APRILGRID and self.spacing_ratio is None:
            raise ValueError("spacing_ratio required for AprilGrid board definitions")
        if self.dictionary not in SUPPORTED_OPENCV_TAG_FAMILIES:
            raise ValueError(f"Unsupported board dictionary: {self.dictionary}")
        return self
