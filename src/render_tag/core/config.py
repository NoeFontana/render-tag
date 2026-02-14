"""
Configuration module for render-tag synthetic data generation.

This module defines the configuration schema using Pydantic v2, providing
strict validation and type safety for all generation parameters.
"""

from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from render_tag.core.schema import (
    SensorNoiseConfig,
)


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


class LightingPreset(str, Enum):
    """Preset lighting configurations for different environments."""

    FACTORY = "factory"
    WAREHOUSE = "warehouse"
    OUTDOOR_INDUSTRIAL = "outdoor_industrial"


class LayoutMode(str, Enum):
    """Layout mode for tag placement in scenes."""

    PLAIN = "plain"  # Tags equidistant, no connecting pattern
    CHECKERBOARD = "cb"  # ChArUco board: tags in alternating squares
    APRILGRID = "aprilgrid"  # Kalibr AprilGrid: tags in every cell + corner dots


class SamplingMode(str, Enum):
    """Camera sampling mode for dataset tuning."""

    RANDOM = "random"  # Random sphere sampling
    DISTANCE = "distance"  # Varying distance to target
    ANGLE = "angle"  # Varying tilt angle to target


class PPMConstraint(BaseModel):
    """Configuration for Pixels Per Module (PPM) driven sampling."""

    min: float = Field(default=5.0, gt=0, description="Minimum target PPM")
    max: float = Field(default=100.0, gt=0, description="Maximum target PPM")
    distribution: Literal["uniform"] = Field(default="uniform", description="Sampling distribution")


class EvaluationScope(str, Enum):
    """Explicit capability contracts for multi-functional datasets."""

    DETECTION = "detection"  # Metrics: Recall, Precision, F1
    CORNER_PRECISION = "corner_accuracy"  # Metrics: RMSE, Max Error (px)
    POSE_ACCURACY = "pose_estimation"  # Metrics: Translation Error (m), Rotation Error (deg)
    CALIBRATION = "calibration"  # Metrics: Intrinsics Convergence, Reprojection Error


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


# Maximum ID (exclusive) for each tag family
TAG_MAX_IDS: dict[str, int] = {
    "tag16h5": 16,
    "tag25h9": 35,
    "tag36h10": 2320,
    "tag36h11": 587,
    "tagCircle21h7": 587,
    "tagCircle49h12": 587,
    "tagCustom48h12": 587,
    "tagStandard41h12": 587,
    "tagStandard52h13": 587,
    "DICT_4X4_50": 50,
    "DICT_4X4_100": 100,
    "DICT_4X4_250": 250,
    "DICT_4X4_1000": 1000,
    "DICT_5X5_50": 50,
    "DICT_5X5_100": 100,
    "DICT_5X5_250": 250,
    "DICT_5X5_1000": 1000,
    "DICT_6X6_50": 50,
    "DICT_6X6_100": 100,
    "DICT_6X6_250": 250,
    "DICT_6X6_1000": 1000,
    "DICT_7X7_50": 50,
    "DICT_7X7_100": 100,
    "DICT_7X7_250": 250,
    "DICT_7X7_1000": 1000,
    "DICT_ARUCO_ORIGINAL": 1024,
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


class SeedConfig(BaseModel):
    """Hierarchical random seed configuration.

    Allows locking specific aspects of randomness while varying others.
    """

    global_seed: int = Field(default=42, ge=0, description="Master seed")
    layout: int | None = Field(default=None, description="Override for layout generation")
    lighting: int | None = Field(default=None, description="Override for lighting generation")
    camera: int | None = Field(default=None, description="Override for camera sampling")
    noise: int | None = Field(default=None, description="Seed for image noise/augmentation")

    @property
    def layout_seed(self) -> int:
        return self.layout if self.layout is not None else self.global_seed

    @property
    def lighting_seed(self) -> int:
        return self.lighting if self.lighting is not None else self.global_seed

    @property
    def camera_seed(self) -> int:
        return self.camera if self.camera is not None else self.global_seed

    @property
    def noise_seed(self) -> int:
        return self.noise if self.noise is not None else self.global_seed + 1


class SensorDynamicsConfig(BaseModel):
    """Configuration for dynamic sensor artifacts (Motion Blur, Rolling Shutter)."""

    velocity_mean: float = Field(
        default=0.0, ge=0, description="Mean camera velocity (m/s) for motion blur"
    )
    velocity_std: float = Field(default=0.0, ge=0, description="Std dev of camera velocity")
    shutter_time_ms: float = Field(
        default=10.0, ge=0, description="Shutter open time in milliseconds"
    )
    rolling_shutter_duration_ms: float = Field(
        default=0.0, ge=0, description="Rolling shutter scan duration in milliseconds"
    )


class DatasetConfig(BaseModel):
    """Dataset output configuration."""

    output_dir: Path = Field(
        default=Path("output"), description="Output directory for generated data"
    )
    seeds: SeedConfig = Field(default_factory=SeedConfig, description="Random seeds")
    num_scenes: int = Field(default=1, gt=0, description="Number of scenes to generate")
    intent: str | None = Field(
        default=None,
        description="[DEPRECATED] Intent/Goal of this dataset. Use evaluation_scopes instead.",
    )
    evaluation_scopes: list[EvaluationScope] = Field(
        default_factory=lambda: [EvaluationScope.DETECTION],
        description="Explicit whitelists of valid evaluation metrics",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata for the dataset"
    )

    @model_validator(mode="before")
    @classmethod
    def map_intent_to_scopes(cls, data: Any) -> Any:
        if isinstance(data, dict) and "intent" in data and "evaluation_scopes" not in data:
            # If intent is provided but evaluation_scopes is not, map it
            intent_val = data["intent"]
            if intent_val == "calibration":
                data["evaluation_scopes"] = [EvaluationScope.CALIBRATION]
            elif "pose" in str(intent_val):
                data["evaluation_scopes"] = [
                    EvaluationScope.DETECTION,
                    EvaluationScope.POSE_ACCURACY,
                    EvaluationScope.CORNER_PRECISION,
                ]
                # Default for other intents is already handled by default_factory
        return data

    # Backwards compatibility property
    @property
    def seed(self) -> int:
        return self.seeds.global_seed

    @model_validator(mode="before")
    @classmethod
    def map_legacy_seed(cls, data: Any) -> Any:
        if isinstance(data, dict) and "seed" in data:
            if "seeds" not in data:
                data["seeds"] = {}
            if isinstance(data["seeds"], dict):
                data["seeds"]["global_seed"] = data["seed"]
        return data


class CameraIntrinsics(BaseModel):
    """Camera intrinsic parameters.

    Supports multiple ways to specify intrinsics:
    - Direct K matrix (3x3)
    - Focal length + principal point
    - Focal length + sensor size (auto-compute principal point)

    If K matrix is provided, it takes precedence over other parameters.
    """

    # K matrix (3x3 intrinsic matrix) - optional, overrides other params if set
    k_matrix: list[list[float]] | None = Field(
        default=None,
        description="3x3 camera intrinsic matrix [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]",
    )

    # Individual intrinsic parameters
    focal_length_x: float | None = Field(
        default=None, gt=0, description="Focal length in x (pixels)"
    )
    focal_length_y: float | None = Field(
        default=None, gt=0, description="Focal length in y (pixels)"
    )
    focal_length: float | None = Field(
        default=None,
        gt=0,
        description="Single focal length (used for both x and y if fx/fy not set)",
    )
    principal_point_x: float | None = Field(
        default=None, description="Principal point x coordinate (cx)"
    )
    principal_point_y: float | None = Field(
        default=None, description="Principal point y coordinate (cy)"
    )

    # Sensor-based specification
    sensor_width_mm: float | None = Field(
        default=None, gt=0, description="Sensor width in millimeters"
    )
    focal_length_mm: float | None = Field(
        default=None, gt=0, description="Focal length in millimeters"
    )

    # Lens distortion coefficients (OpenCV convention)
    k1: float = Field(default=0.0, description="Radial distortion coefficient k1")
    k2: float = Field(default=0.0, description="Radial distortion coefficient k2")
    k3: float = Field(default=0.0, description="Radial distortion coefficient k3")
    p1: float = Field(default=0.0, description="Tangential distortion coefficient p1")
    p2: float = Field(default=0.0, description="Tangential distortion coefficient p2")

    @field_validator("k_matrix")
    @classmethod
    def validate_k_matrix(cls, v: list[list[float]] | None) -> list[list[float]] | None:
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

    # Standard 2026 HD Perception Baseline
    resolution: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]] = Field(
        default=(1920, 1080), description="Image resolution (width, height)"
    )
    fov: float = Field(default=70.0, gt=0, lt=180, description="Field of view in degrees")
    samples_per_scene: int = Field(
        default=10, gt=0, description="Number of camera samples per scene"
    )
    intrinsics: CameraIntrinsics = Field(
        default_factory=CameraIntrinsics, description="Camera intrinsic parameters"
    )
    # Sampling parameters
    min_distance: float = Field(default=0.5, gt=0, description="Minimum camera distance")
    max_distance: float = Field(default=2.0, gt=0, description="Maximum camera distance")
    min_elevation: float = Field(default=0.3, ge=0, le=1, description="Min elevation")
    max_elevation: float = Field(default=0.9, ge=0, le=1, description="Max elevation")
    elevation: float | None = Field(default=None, description="Fixed elevation")
    azimuth: float | None = Field(default=None, description="Fixed azimuth")
    min_roll: float = Field(default=0.0, description="Minimum in-plane rotation (degrees)")
    max_roll: float = Field(default=0.0, description="Maximum in-plane rotation (degrees)")

    ppm_constraint: PPMConstraint | None = Field(
        default=None, description="Constraint for Pixels Per Module (PPM) driven sampling"
    )

    # Sensor Dynamics (Motion Blur, Rolling Shutter)
    sensor_dynamics: SensorDynamicsConfig = Field(
        default_factory=SensorDynamicsConfig,
        description="Dynamic sensor artifacts configuration",
    )

    # Depth of Field
    fstop: float | None = Field(
        default=None, gt=0, description="Lens aperture (f-stop). None=Infinite focus"
    )
    focus_distance: float | None = Field(
        default=None,
        gt=0,
        description="Fixed focus distance. None=Auto-focus on target",
    )

    # Sensor Noise/Distortion
    iso_noise: float = Field(
        default=0.0, ge=0, description="Simulated sensor gain/ISO noise level (0-1)"
    )
    sensor_noise_sigma: float = Field(
        default=0.002,
        ge=0,
        description="Additive Gaussian Noise (sigma)",
    )
    sensor_noise: SensorNoiseConfig | None = Field(
        default=None, description="Parametric sensor noise configuration"
    )

    # 2026 High Dynamic Range (HDR) Baseline
    # Simulates the sensor's ability to recover shadow detail
    dynamic_range_db: float = Field(default=120.0, description="Sensor dynamic range in dB")

    # Tag Sizing Constraints (Staff Engineer Pattern: Quality Gates at Sampling)
    min_tag_pixels: float | None = Field(
        default=None, description="Minimum area in pixels for a tag to be valid"
    )
    max_tag_pixels: float | None = Field(
        default=None, description="Maximum area in pixels for a tag to be valid"
    )

    # Tone Mapping: 'linear' for raw, 'srgb' for standard, 'filmic' for modern ISP simulation
    tone_mapping: Literal["linear", "srgb", "filmic"] = Field(
        default="filmic", description="Tone mapping operator"
    )

    # ISO / Gain simulation: Higher gain = more 'salt and pepper' noise
    iso: int = Field(default=100, ge=100, le=6400, description="Camera ISO setting")

    @model_validator(mode="before")
    @classmethod
    def map_legacy_sensor_dynamics(cls, data: Any) -> Any:
        """Map top-level legacy sensor dynamics fields to the nested grouping."""
        if not isinstance(data, dict):
            return data

        dynamics = data.get("sensor_dynamics", {})
        if not isinstance(dynamics, dict):
            # If it's already an object or invalid, let pydantic handle it
            return data

        # Map legacy fields if they exist at top level and NOT in sensor_dynamics already
        legacy_fields = ["velocity_mean", "velocity_std", "shutter_time_ms"]
        for field in legacy_fields:
            if field in data and field not in dynamics:
                dynamics[field] = data.pop(field)

        # Handle 'shutter_speed' alias (seconds) -> shutter_time_ms (milliseconds)
        if "shutter_speed" in data:
            dynamics["shutter_time_ms"] = data.pop("shutter_speed") * 1000.0

        # Handle 'rolling_shutter_readout' alias -> rolling_shutter_duration_ms
        if "rolling_shutter_readout" in data:
            dynamics["rolling_shutter_duration_ms"] = data.pop("rolling_shutter_readout")

        if dynamics:
            data["sensor_dynamics"] = dynamics

        return data

    # Backwards compatibility properties
    @property
    def velocity_mean(self) -> float:
        return self.sensor_dynamics.velocity_mean

    @velocity_mean.setter
    def velocity_mean(self, value: float) -> None:
        self.sensor_dynamics.velocity_mean = value

    @property
    def velocity_std(self) -> float:
        return self.sensor_dynamics.velocity_std

    @velocity_std.setter
    def velocity_std(self, value: float) -> None:
        self.sensor_dynamics.velocity_std = value

    @property
    def shutter_time_ms(self) -> float:
        return self.sensor_dynamics.shutter_time_ms

    @shutter_time_ms.setter
    def shutter_time_ms(self, value: float) -> None:
        self.sensor_dynamics.shutter_time_ms = value

    @property
    def width(self) -> int:
        return self.resolution[0]

    @property
    def height(self) -> int:
        return self.resolution[1]

    @property
    def distance(self) -> float | None:
        """Alias for fixed distance if set."""
        return None  # We use min/max distance for sampling by default

    @property
    def elevation_fixed(self) -> float | None:
        """Alias for fixed elevation if set."""
        return self.elevation

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

        cx = (
            intrinsics.principal_point_x
            if intrinsics.principal_point_x is not None
            else self.width / 2.0
        )
        cy = (
            intrinsics.principal_point_y
            if intrinsics.principal_point_y is not None
            else self.height / 2.0
        )

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


class MaterialConfig(BaseModel):
    """Configuration for tag material properties (Domain Randomization)."""

    randomize: bool = Field(default=False, description="Enable material randomization")

    # Range for Roughness (0.0 = Mirror, 1.0 = Matte)
    # Default 0.4 (Matte-Finish Acrylic)
    roughness_min: float = Field(default=0.4, ge=0.0, le=1.0)
    roughness_max: float = Field(default=0.4, ge=0.0, le=1.0)

    # Range for Specular (0.0 = No highlights, 1.0 = Strong highlights)
    # Default 0.2 (Plastic/Cardstock)
    specular_min: float = Field(default=0.2, ge=0.0, le=1.0)
    specular_max: float = Field(default=0.2, ge=0.0, le=1.0)


class TagConfig(BaseModel):
    """AprilTag configuration."""

    family: TagFamily = Field(default=TagFamily.TAG36H11, description="AprilTag family")
    size_meters: float = Field(default=0.1, gt=0, description="Tag size in meters (outer edge)")
    margin_bits: int = Field(
        default=1, ge=0, description="Width of the white quiet zone in bits"
    )
    texture_path: Path | None = Field(default=None, description="Path to tag texture directory")
    material: MaterialConfig = Field(default_factory=MaterialConfig)


class LightingConfig(BaseModel):
    """Lighting configuration."""

    intensity_min: float = Field(default=50.0, ge=0, description="Minimum light intensity")
    intensity_max: float = Field(default=500.0, ge=0, description="Maximum light intensity")

    # Range for light source radius (shadow softness)
    radius_min: float = Field(
        default=0.0, ge=0.0, description="Minimum light radius (shadow softness)"
    )
    radius_max: float = Field(default=0.0, ge=0.0, description="Maximum light radius")

    @model_validator(mode="after")
    def validate_ranges(self) -> "LightingConfig":
        if self.intensity_min > self.intensity_max:
            raise ValueError("intensity_min must be <= intensity_max")
        if self.radius_min > self.radius_max:
            raise ValueError("radius_min must be <= radius_max")
        return self


def get_lighting_preset(preset: LightingPreset) -> LightingConfig:
    """Get a LightingConfig for a specific preset."""
    if preset == LightingPreset.FACTORY:
        return LightingConfig(
            intensity_min=200.0,
            intensity_max=400.0,
            radius_min=0.1,
            radius_max=0.5,
        )
    elif preset == LightingPreset.WAREHOUSE:
        return LightingConfig(
            intensity_min=50.0,
            intensity_max=200.0,
            radius_min=0.05,
            radius_max=0.2,
        )
    elif preset == LightingPreset.OUTDOOR_INDUSTRIAL:
        return LightingConfig(
            intensity_min=800.0,
            intensity_max=1200.0,
            radius_min=0.0,
            radius_max=0.02,
        )
    # Default
    return LightingConfig()


class SceneConfig(BaseModel):
    """Scene configuration."""

    lighting: LightingConfig = Field(
        default_factory=LightingConfig, description="Lighting parameters"
    )
    lighting_preset: LightingPreset | None = Field(
        default=None, description="Lighting preset override (factory, warehouse, etc.)"
    )
    background_hdri: Path | None = Field(default=None, description="Path to HDRI background image")
    texture_dir: Path | None = Field(
        default=None, description="Path to texture directory for backgrounds"
    )

    # Tiling scale: 1.0 = stretched (Easy), 20.0 = highly repetitive (Hard)
    texture_scale_min: float = Field(default=1.0, gt=0, description="Min texture tiling scale")
    texture_scale_max: float = Field(default=1.0, gt=0, description="Max texture tiling scale")

    # Rotation: Adds variation to the same texture asset
    random_texture_rotation: bool = Field(default=True, description="Randomly rotate floor texture")

    @model_validator(mode="after")
    def validate_scale_range(self) -> "SceneConfig":
        if self.texture_scale_min > self.texture_scale_max:
            raise ValueError("texture_scale_min must be <= texture_scale_max")

        # Apply lighting preset if specified
        if self.lighting_preset:
            self.lighting = get_lighting_preset(self.lighting_preset)

        return self


class PhysicsConfig(BaseModel):
    """Physics simulation configuration."""

    drop_height: float = Field(default=0.2, ge=0, description="Drop height in meters")
    scatter_radius: float = Field(default=0.5, gt=0, description="Scatter radius in meters")


class ScenarioConfig(BaseModel):
    """Configuration for a generation scenario.

    Defines the layout mode and tag configuration for scene generation.
    """

    layout: LayoutMode = Field(
        default=LayoutMode.PLAIN, description="Layout mode for tag placement"
    )
    tag_families: list[TagFamily] = Field(
        default=[TagFamily.TAG36H11],
        description="Tag families to use in this scenario",
    )
    layouts: list[LayoutMode] | None = Field(
        default=None,
        description="Optional list of layouts to iterate through across scenes",
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
        description="Size of black corner squares in meters (AprilGrid only)",
    )
    square_size: float = Field(
        default=0.12,
        gt=0,
        description="Size of each grid cell for checkerboard/AprilGrid layouts (meters)",
    )
    marker_margin: float = Field(
        default=0.01,
        ge=0,
        description="Margin between marker edge and cell edge (meters)",
    )
    tag_spacing_bits: int | None = Field(
        default=2,
        description="Spacing between tags in number of bits (relative to tag grid size)",
    )

    sampling_mode: SamplingMode = Field(
        default=SamplingMode.RANDOM,
        description="Sampling mode for camera poses (random, distance, angle)",
    )
    azimuth: float | None = Field(
        default=None,
        description="Fixed azimuth in radians for deterministic alignment",
    )
    flying: bool = Field(
        default=False,
        description="If True, tags fly in space without a floor board",
    )
    use_board: bool = Field(
        default=True,
        description="If True, adds a board/margin behind the tags",
    )

    @field_validator("tags_per_scene")
    @classmethod
    def validate_tags_per_scene(cls, v: tuple[int, int]) -> tuple[int, int]:
        if v[0] < 1:
            raise ValueError("Minimum tags per scene must be >= 1")
        if v[0] > v[1]:
            raise ValueError("Min tags must be <= max tags")
        return v


class SequenceConfig(BaseModel):
    """Configuration for temporal sequences and motion."""

    # Temporal Baseline: 30 FPS or 60 FPS
    fps: int = Field(default=30, gt=0, description="Frames per second")

    # Motion Continuity: If True, uses Physics to calculate next pose
    continuous_motion: bool = Field(
        default=True,
        description="Enable physics-based motion continuity",
    )

    # Sub-frame sampling: Critical for high-fidelity Motion Blur
    motion_blur_samples: int = Field(
        default=8,
        ge=1,
        description="Number of sub-frame samples for motion blur",
    )


class EnvironmentConfig(BaseModel):
    """Configuration for environmental distractors and atmospheric effects."""

    # Distractors: Random objects (chairs, tools) that might partially occlude tags
    distractor_density: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Probability of distractor occlusion per scene",
    )

    # Atmospheric interference: Simulates dust or fog in industrial environments
    # This tests the 'Soft Decoding' robustness of locus-tag
    fog_intensity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Volumetric fog intensity (0-1)",
    )


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
    sequence: SequenceConfig = Field(
        default_factory=SequenceConfig, description="Temporal sequence configuration"
    )
    environment: EnvironmentConfig = Field(
        default_factory=EnvironmentConfig, description="Environmental distractors and effects"
    )

    # Asset Management
    force_reload_assets: bool = Field(
        default=False, description="Force re-download/reload of assets"
    )


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
    if "output_dir" in flat:
        nested["dataset"]["output_dir"] = flat["output_dir"]
    if "seed" in flat:
        nested["dataset"]["seeds"] = {"global_seed": flat["seed"]}

    return nested
