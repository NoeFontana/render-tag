"""
Configuration module for render-tag synthetic data generation.

This module defines the configuration schema using Pydantic v2, providing
strict validation and type safety for all generation parameters.
"""

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class TagFamily(str, Enum):
    """Supported fiducial marker families.

    Includes both AprilTag families and ArUco dictionaries.
    """

    # AprilTag families
    TAG36H11 = "tag36h11"
    TAG36H10 = "tag36h10"
    TAG25H9 = "tag25h9"
    TAG16H5 = "tag16h5"
    TAGCIRCLE21H7 = "tagCircle21h7"
    TAGCIRCLE49H12 = "tagCircle49h12"
    TAGCUSTOM48H12 = "tagCustom48h12"
    TAGSTANDARD41H12 = "tagStandard41h12"
    TAGSTANDARD52H13 = "tagStandard52h13"

    # ArUco dictionaries (OpenCV standard)
    ARUCO_4X4_50 = "DICT_4X4_50"
    ARUCO_4X4_100 = "DICT_4X4_100"
    ARUCO_4X4_250 = "DICT_4X4_250"
    ARUCO_4X4_1000 = "DICT_4X4_1000"
    ARUCO_5X5_50 = "DICT_5X5_50"
    ARUCO_5X5_100 = "DICT_5X5_100"
    ARUCO_5X5_250 = "DICT_5X5_250"
    ARUCO_5X5_1000 = "DICT_5X5_1000"
    ARUCO_6X6_50 = "DICT_6X6_50"
    ARUCO_6X6_100 = "DICT_6X6_100"
    ARUCO_6X6_250 = "DICT_6X6_250"
    ARUCO_6X6_1000 = "DICT_6X6_1000"
    ARUCO_7X7_50 = "DICT_7X7_50"
    ARUCO_7X7_100 = "DICT_7X7_100"
    ARUCO_7X7_250 = "DICT_7X7_250"
    ARUCO_7X7_1000 = "DICT_7X7_1000"
    ARUCO_ORIGINAL = "DICT_ARUCO_ORIGINAL"

    @property
    def is_apriltag(self) -> bool:
        """Check if this is an AprilTag family."""
        return self.value.startswith("tag")

    @property
    def is_aruco(self) -> bool:
        """Check if this is an ArUco dictionary."""
        return self.value.startswith("DICT_")


class LayoutMode(str, Enum):
    """Layout mode for tag placement in scenes."""
    
    PLAIN = "plain"  # Tags equidistant, no connecting pattern
    CHECKERBOARD = "cb"  # Tags connected by black corner squares


# Bit counts for each tag family (used for minimum pixel area calculation)
TAG_BIT_COUNTS: dict[str, int] = {
    # AprilTag families
    "tag36h11": 36,
    "tag36h10": 36,
    "tag25h9": 25,
    "tag16h5": 16,
    "tagCircle21h7": 21,
    "tagCircle49h12": 49,
    "tagCustom48h12": 48,
    "tagStandard41h12": 41,
    "tagStandard52h13": 52,
    # ArUco dictionaries
    "DICT_4X4_50": 16,
    "DICT_4X4_100": 16,
    "DICT_4X4_250": 16,
    "DICT_4X4_1000": 16,
    "DICT_5X5_50": 25,
    "DICT_5X5_100": 25,
    "DICT_5X5_250": 25,
    "DICT_5X5_1000": 25,
    "DICT_6X6_50": 36,
    "DICT_6X6_100": 36,
    "DICT_6X6_250": 36,
    "DICT_6X6_1000": 36,
    "DICT_7X7_50": 49,
    "DICT_7X7_100": 49,
    "DICT_7X7_250": 49,
    "DICT_7X7_1000": 49,
    "DICT_ARUCO_ORIGINAL": 25,
}


def get_min_pixel_area(tag_family: str | TagFamily) -> int:
    """Get the minimum pixel area for a tag to be considered valid.
    
    The minimum area equals the number of data bits in the tag.
    
    Args:
        tag_family: Tag family name or enum value
        
    Returns:
        Minimum pixel area (= bit count)
    """
    if isinstance(tag_family, TagFamily):
        tag_family = tag_family.value
    return TAG_BIT_COUNTS.get(tag_family, 36)  # Default to 36 if unknown



class DatasetConfig(BaseModel):
    """Dataset output configuration."""

    output_dir: Path = Field(default=Path("output"), description="Output directory for generated data")
    seed: int = Field(default=42, description="Random seed for reproducibility")
    num_scenes: int = Field(default=1, gt=0, description="Number of scenes to generate")

    @field_validator("seed")
    @classmethod
    def validate_seed(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Seed must be non-negative")
        return v


class CameraIntrinsics(BaseModel):
    """Camera intrinsic parameters.

    Supports multiple ways to specify intrinsics:
    - Direct K matrix (3x3)
    - Focal length + principal point
    - Focal length + sensor size (auto-compute principal point)

    If K matrix is provided, it takes precedence over other parameters.
    """

    # K matrix (3x3 intrinsic matrix) - optional, overrides other params if set
    k_matrix: Optional[list[list[float]]] = Field(
        default=None,
        description="3x3 camera intrinsic matrix [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]",
    )

    # Individual intrinsic parameters
    focal_length_x: Optional[float] = Field(default=None, gt=0, description="Focal length in x (pixels)")
    focal_length_y: Optional[float] = Field(default=None, gt=0, description="Focal length in y (pixels)")
    focal_length: Optional[float] = Field(
        default=None, gt=0, description="Single focal length (used for both x and y if fx/fy not set)"
    )
    principal_point_x: Optional[float] = Field(default=None, description="Principal point x coordinate (cx)")
    principal_point_y: Optional[float] = Field(default=None, description="Principal point y coordinate (cy)")

    # Sensor-based specification
    sensor_width_mm: Optional[float] = Field(default=None, gt=0, description="Sensor width in millimeters")
    focal_length_mm: Optional[float] = Field(default=None, gt=0, description="Focal length in millimeters")

    # Lens distortion coefficients (OpenCV convention)
    k1: float = Field(default=0.0, description="Radial distortion coefficient k1")
    k2: float = Field(default=0.0, description="Radial distortion coefficient k2")
    k3: float = Field(default=0.0, description="Radial distortion coefficient k3")
    p1: float = Field(default=0.0, description="Tangential distortion coefficient p1")
    p2: float = Field(default=0.0, description="Tangential distortion coefficient p2")

    @field_validator("k_matrix")
    @classmethod
    def validate_k_matrix(cls, v: Optional[list[list[float]]]) -> Optional[list[list[float]]]:
        if v is None:
            return v
        if len(v) != 3 or any(len(row) != 3 for row in v):
            raise ValueError("K matrix must be 3x3")
        # Check that it's a valid intrinsic matrix format
        if v[2][0] != 0 or v[2][1] != 0 or v[2][2] != 1:
            raise ValueError("K matrix last row must be [0, 0, 1]")
        if v[0][1] != 0:
            raise ValueError("K matrix must have zero skew (K[0][1] = 0)")
        return v

    def get_distortion_coeffs(self) -> tuple[float, float, float, float, float]:
        """Return distortion coefficients in OpenCV order (k1, k2, p1, p2, k3)."""
        return (self.k1, self.k2, self.p1, self.p2, self.k3)


class CameraConfig(BaseModel):
    """Camera configuration for rendering."""

    resolution: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]] = Field(
        default=(640, 480), description="Image resolution (width, height)"
    )
    fov: float = Field(default=60.0, gt=0, lt=180, description="Field of view in degrees")
    samples_per_scene: int = Field(default=10, gt=0, description="Number of camera samples per scene")
    intrinsics: CameraIntrinsics = Field(default_factory=CameraIntrinsics, description="Camera intrinsic parameters")

    @property
    def width(self) -> int:
        return self.resolution[0]

    @property
    def height(self) -> int:
        return self.resolution[1]

    def get_k_matrix(self) -> list[list[float]]:
        """Compute the K matrix from available parameters.

        Priority:
        1. Explicit k_matrix
        2. focal_length_x/y + principal_point
        3. focal_length + resolution (centered principal point)
        4. sensor_width_mm + focal_length_mm + resolution
        5. Default from FOV + resolution
        """
        intrinsics = self.intrinsics

        if intrinsics.k_matrix is not None:
            return intrinsics.k_matrix

        cx = intrinsics.principal_point_x if intrinsics.principal_point_x is not None else self.width / 2.0
        cy = intrinsics.principal_point_y if intrinsics.principal_point_y is not None else self.height / 2.0

        # Try focal_length_x/y
        if intrinsics.focal_length_x is not None and intrinsics.focal_length_y is not None:
            fx, fy = intrinsics.focal_length_x, intrinsics.focal_length_y
        elif intrinsics.focal_length is not None:
            fx = fy = intrinsics.focal_length
        elif intrinsics.sensor_width_mm is not None and intrinsics.focal_length_mm is not None:
            # Compute from sensor dimensions
            fx = fy = (intrinsics.focal_length_mm / intrinsics.sensor_width_mm) * self.width
        else:
            # Default: compute from FOV
            import math

            fx = fy = self.width / (2.0 * math.tan(math.radians(self.fov / 2.0)))

        return [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]]


class TagConfig(BaseModel):
    """AprilTag configuration."""

    family: TagFamily = Field(default=TagFamily.TAG36H11, description="AprilTag family")
    size_meters: float = Field(default=0.1, gt=0, description="Tag size in meters (outer edge)")
    texture_path: Optional[Path] = Field(default=None, description="Path to tag texture directory")


class LightingConfig(BaseModel):
    """Lighting configuration."""

    intensity_min: float = Field(default=50.0, ge=0, description="Minimum light intensity")
    intensity_max: float = Field(default=500.0, ge=0, description="Maximum light intensity")

    @model_validator(mode="after")
    def validate_intensity_range(self) -> "LightingConfig":
        if self.intensity_min > self.intensity_max:
            raise ValueError("intensity_min must be <= intensity_max")
        return self


class SceneConfig(BaseModel):
    """Scene configuration."""

    lighting: LightingConfig = Field(default_factory=LightingConfig, description="Lighting parameters")
    background_hdri: Optional[Path] = Field(default=None, description="Path to HDRI background image")
    texture_dir: Optional[Path] = Field(default=None, description="Path to texture directory for backgrounds")


class PhysicsConfig(BaseModel):
    """Physics simulation configuration."""

    drop_height: float = Field(default=1.5, gt=0, description="Drop height in meters")
    scatter_radius: float = Field(default=0.5, gt=0, description="Scatter radius in meters")


class ScenarioConfig(BaseModel):
    """Configuration for a generation scenario.
    
    Defines the layout mode and tag configuration for scene generation.
    """
    
    layout: LayoutMode = Field(default=LayoutMode.PLAIN, description="Layout mode for tag placement")
    tag_families: list[TagFamily] = Field(
        default=[TagFamily.TAG36H11],
        description="Tag families to use in this scenario",
    )
    tags_per_scene: tuple[int, int] = Field(
        default=(1, 5),
        description="Range of tags per scene (min, max)",
    )
    # Checkerboard-specific settings
    grid_size: tuple[int, int] = Field(
        default=(3, 3),
        description="Grid of tags for checkerboard layout (cols, rows)",
    )
    corner_size: float = Field(
        default=0.01,
        gt=0,
        description="Size of black corner squares in meters (checkerboard only)",
    )
    tag_spacing: float = Field(
        default=0.05,
        gt=0,
        description="Spacing between tags in meters (plain layout only)",
    )

    @field_validator("tags_per_scene")
    @classmethod
    def validate_tags_per_scene(cls, v: tuple[int, int]) -> tuple[int, int]:
        if v[0] < 1:
            raise ValueError("Minimum tags per scene must be >= 1")
        if v[0] > v[1]:
            raise ValueError("Min tags must be <= max tags")
        return v


class GenConfig(BaseModel):
    """Root configuration for synthetic data generation.

    This is the single source of truth for all generation parameters.
    """

    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    tag: TagConfig = Field(default_factory=TagConfig)
    scene: SceneConfig = Field(default_factory=SceneConfig)
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    scenario: ScenarioConfig = Field(default_factory=ScenarioConfig)


def load_config(path: Path | str) -> GenConfig:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Validated GenConfig instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If the config is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    # Handle flat config format (legacy compatibility)
    if "resolution" in data and "camera" not in data:
        data = _convert_flat_config(data)

    return GenConfig.model_validate(data)


def _convert_flat_config(flat: dict) -> dict:
    """Convert flat config format to nested format for backwards compatibility."""
    nested: dict = {
        "dataset": {},
        "camera": {},
        "tag": {},
        "scene": {},
        "physics": {},
    }

    # Map flat keys to nested structure
    if "resolution" in flat:
        nested["camera"]["resolution"] = flat["resolution"]
    if "samples" in flat:
        nested["camera"]["samples_per_scene"] = flat["samples"]
    if "tag_family" in flat:
        nested["tag"]["family"] = flat["tag_family"]
    if "lighting" in flat:
        nested["scene"]["lighting"] = flat["lighting"]
    if "backgrounds" in flat:
        if "hdri_path" in flat["backgrounds"]:
            nested["scene"]["background_hdri"] = flat["backgrounds"]["hdri_path"]
        if "texture_dir" in flat["backgrounds"]:
            nested["scene"]["texture_dir"] = flat["backgrounds"]["texture_dir"]
    if "physics" in flat:
        nested["physics"] = flat["physics"]
    if "output_dir" in flat:
        nested["dataset"]["output_dir"] = flat["output_dir"]
    if "seed" in flat:
        nested["dataset"]["seed"] = flat["seed"]

    return nested
