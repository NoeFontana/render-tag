"""
Configuration module for render-tag synthetic data generation.

This module defines the configuration schema using Pydantic v2, providing
strict validation and type safety for all generation parameters.
"""

import math
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from render_tag.core.constants import CURRENT_SCHEMA_VERSION, TAG_BIT_COUNTS
from render_tag.core.schema import (
    RendererConfig,
    SensorNoiseConfig,
)
from render_tag.core.schema.base import TagFamily
from render_tag.core.schema.subject import (
    SubjectConfig,
    TagSubjectConfig,
)


class LayoutMode(str, Enum):
    """Layout mode for tag placement in scenes."""

    PLAIN = "plain"  # Tags equidistant, no connecting pattern
    CHECKERBOARD = "cb"  # ChArUco board: tags in alternating squares
    APRILGRID = "aprilgrid"  # Kalibr AprilGrid: tags in every cell + corner dots
    BOARD = "board"  # Calibration Board: single rigid body with high-fidelity texture


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


# Maximum ID (exclusive) for each tag family
TAG_MAX_IDS: dict[str, int] = {
    "tag16h5": 16,
    "tag25h9": 35,
    "tag36h10": 2320,
    "tag36h11": 587,
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
        """Get seed for layout generation."""
        return self.layout if self.layout is not None else self.global_seed

    @property
    def lighting_seed(self) -> int:
        """Get seed for lighting generation."""
        return self.lighting if self.lighting is not None else self.global_seed

    @property
    def camera_seed(self) -> int:
        """Get seed for camera sampling."""
        return self.camera if self.camera is not None else self.global_seed

    @property
    def noise_seed(self) -> int:
        """Get seed for image noise/augmentation."""
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

    model_config = ConfigDict(extra="forbid")

    output_dir: Path = Field(
        default=Path("output"), description="Output directory for generated data"
    )
    seeds: SeedConfig = Field(default_factory=SeedConfig, description="Random seeds")
    num_scenes: int = Field(default=1, gt=0, description="Number of scenes to generate")
    evaluation_scopes: list[EvaluationScope] = Field(
        default_factory=lambda: [EvaluationScope.DETECTION],
        description="Explicit whitelists of valid evaluation metrics",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata for the dataset"
    )

    # Backwards compatibility property
    @property
    def seed(self) -> int:
        """Alias for global_seed for backwards compatibility."""
        return self.seeds.global_seed


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

    # Distortion model selection
    distortion_model: Literal["none", "brown_conrady", "kannala_brandt"] = Field(
        default="none",
        description=(
            "Distortion model: 'none' (pinhole), 'brown_conrady' (5-param radial+tangential),"
            " or 'kannala_brandt' (4-param equidistant fisheye)"
        ),
    )

    # Brown-Conrady (OpenCV plumb_bob) coefficients
    k1: float = Field(default=0.0, description="Radial distortion k1 (brown_conrady)")
    k2: float = Field(default=0.0, description="Radial distortion k2 (brown_conrady)")
    k3: float = Field(default=0.0, description="Radial distortion k3 (brown_conrady)")
    p1: float = Field(default=0.0, description="Tangential distortion p1 (brown_conrady)")
    p2: float = Field(default=0.0, description="Tangential distortion p2 (brown_conrady)")

    # Kannala-Brandt (equidistant fisheye) coefficients
    kb1: float = Field(default=0.0, description="Fisheye distortion k1 (kannala_brandt)")
    kb2: float = Field(default=0.0, description="Fisheye distortion k2 (kannala_brandt)")
    kb3: float = Field(default=0.0, description="Fisheye distortion k3 (kannala_brandt)")
    kb4: float = Field(default=0.0, description="Fisheye distortion k4 (kannala_brandt)")

    @field_validator("k_matrix")
    @classmethod
    def validate_k_matrix(cls, v: list[list[float]] | None) -> list[list[float]] | None:
        """Ensure K matrix is 3x3 and has valid intrinsic properties."""
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

    def get_distortion_coeffs(self) -> tuple[float, ...]:
        """Return distortion coefficients for the active model.

        Returns:
            brown_conrady: (k1, k2, p1, p2, k3) — 5 coefficients
            kannala_brandt: (kb1, kb2, kb3, kb4) — 4 coefficients
            none: empty tuple
        """
        if self.distortion_model == "kannala_brandt":
            return (self.kb1, self.kb2, self.kb3, self.kb4)
        if self.distortion_model == "brown_conrady":
            return (self.k1, self.k2, self.p1, self.p2, self.k3)
        return ()


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

    # Evaluation Margin ("Don't Care" Zone)
    eval_margin_px: int = Field(
        default=0,
        ge=0,
        description=(
            "Pixel-width margin along image edges treated as a 'Don't Care' zone. "
            "Keypoints within this margin receive v=1 (labeled but not visible) in "
            "COCO export instead of v=2. Set to 0 (default) to disable. "
            "Typical value: 5px (half-radius of a standard 11-px Gaussian kernel)."
        ),
    )

    # Tone Mapping: 'linear' for raw, 'srgb' for standard, 'filmic' for modern ISP simulation
    tone_mapping: Literal["linear", "srgb", "filmic"] = Field(
        default="filmic", description="Tone mapping operator"
    )

    # ISO / Gain simulation: Higher gain = more 'salt and pepper' noise
    iso: int = Field(default=100, ge=100, le=6400, description="Camera ISO setting")

    # Opt-in coupling from `iso` to effective noise at recipe-compile time.
    # Off by default so existing fixtures stay bit-reproducible.
    iso_coupling: bool = Field(
        default=False,
        description=(
            "Derive effective iso_noise and synthesize a Gaussian sensor_noise "
            "from `iso` when True. Only fills fields the user left at defaults."
        ),
    )

    # Backwards compatibility properties
    @property
    def velocity_mean(self) -> float:
        """Alias for sensor_dynamics.velocity_mean."""
        return self.sensor_dynamics.velocity_mean

    @velocity_mean.setter
    def velocity_mean(self, value: float) -> None:
        self.sensor_dynamics.velocity_mean = value

    @property
    def velocity_std(self) -> float:
        """Alias for sensor_dynamics.velocity_std."""
        return self.sensor_dynamics.velocity_std

    @velocity_std.setter
    def velocity_std(self, value: float) -> None:
        self.sensor_dynamics.velocity_std = value

    @property
    def shutter_time_ms(self) -> float:
        """Alias for sensor_dynamics.shutter_time_ms."""
        return self.sensor_dynamics.shutter_time_ms

    @shutter_time_ms.setter
    def shutter_time_ms(self, value: float) -> None:
        self.sensor_dynamics.shutter_time_ms = value

    @property
    def width(self) -> int:
        """Image width from resolution."""
        return self.resolution[0]

    @property
    def height(self) -> int:
        """Image height from resolution."""
        return self.resolution[1]

    @property
    def distance(self) -> float | None:
        """Alias for fixed distance if set."""
        return None  # We use min/max distance for sampling by default

    @property
    def elevation_fixed(self) -> float | None:
        """Alias for fixed elevation if set."""
        return self.elevation

    def scale_resolution(self, new_width: int, new_height: int) -> None:
        """Scale camera resolution and adjust intrinsics proportionally.

        Maintains the same Field of View (FOV) by scaling the focal length
        and optical center relative to the resolution change.
        """
        old_w, old_h = self.resolution
        scale_x = new_width / old_w
        scale_y = new_height / old_h

        self.resolution = (new_width, new_height)

        # Scale K matrix if present
        if self.intrinsics.k_matrix is not None:
            k = self.intrinsics.k_matrix
            # Ensure it's a list of lists before modification
            new_k = [list(row) for row in k]
            new_k[0][0] *= scale_x  # fx
            new_k[1][1] *= scale_y  # fy
            new_k[0][2] *= scale_x  # cx
            new_k[1][2] *= scale_y  # cy
            self.intrinsics.k_matrix = new_k

        # Scale individual intrinsic parameters if present
        if self.intrinsics.focal_length_x is not None:
            self.intrinsics.focal_length_x *= scale_x
        if self.intrinsics.focal_length_y is not None:
            self.intrinsics.focal_length_y *= scale_y
        if self.intrinsics.focal_length is not None:
            # If using a single focal length but aspect ratio changes, it becomes ambiguous.
            # We scale it by the X scale for consistency, though fx/fy is preferred.
            self.intrinsics.focal_length *= scale_x

        if self.intrinsics.principal_point_x is not None:
            self.intrinsics.principal_point_x *= scale_x
        if self.intrinsics.principal_point_y is not None:
            self.intrinsics.principal_point_y *= scale_y

    def _focal_length_from_fov(self, distortion_model: str) -> float:
        """Compute the isotropic focal length (px) from self.fov for a given distortion model.

        Kannala-Brandt uses the equidistant projection r = f·θ anchored to the image diagonal,
        keeping all corners within θ < 90° where the fisheye solver converges reliably.
        All other models use the standard pinhole formula.
        """
        fov_half_rad = math.radians(self.fov / 2.0)
        if distortion_model == "kannala_brandt":
            diag_half = math.sqrt((self.width / 2.0) ** 2 + (self.height / 2.0) ** 2)
            return diag_half / fov_half_rad
        return self.width / (2.0 * math.tan(fov_half_rad))

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
            fx = fy = self._focal_length_from_fov(intrinsics.distortion_model)

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

    model_config = ConfigDict(extra="forbid")

    margin_bits: int = Field(default=1, ge=0, description="Width of the white quiet zone in bits")
    texture_path: Path | None = Field(default=None, description="Path to tag texture directory")
    material: MaterialConfig = Field(default_factory=MaterialConfig)


class DirectionalLightConfig(BaseModel):
    """Single directional (SUN) light overlay on top of the sampled hemisphere.

    Azimuth is measured CCW from the +X axis around +Z; elevation is the angle
    above the XY horizon. A SUN at (azimuth=0, elevation=0) sits on the +X
    horizon and illuminates the scene toward the origin. The compiler emits one
    additional ``LightRecipe(type='SUN', ...)`` when this is set; the default
    ``None`` leaves hemispheric POINT sampling byte-identical to pre-Phase-3.
    """

    azimuth: float = Field(..., description="Azimuth angle in radians, CCW from +X around +Z")
    elevation: float = Field(
        ...,
        ge=0.0,
        le=math.pi / 2,
        description="Elevation in radians above the XY horizon (0=horizon, pi/2=zenith)",
    )
    intensity: float = Field(
        default=5.0,
        gt=0.0,
        description="SUN radiance in W/m^2 (Blender SUN units)",
    )
    color: list[float] = Field(
        default_factory=lambda: [1.0, 1.0, 1.0],
        min_length=3,
        max_length=3,
        description="Linear RGB color multiplier",
    )


class LightingConfig(BaseModel):
    """Lighting configuration."""

    intensity_min: float = Field(default=50.0, ge=0, description="Minimum light intensity")
    intensity_max: float = Field(default=500.0, ge=0, description="Maximum light intensity")

    # Range for light source radius (shadow softness)
    radius_min: float = Field(
        default=0.0, ge=0.0, description="Minimum light radius (shadow softness)"
    )
    radius_max: float = Field(default=0.0, ge=0.0, description="Maximum light radius")

    directional: list[DirectionalLightConfig] = Field(
        default_factory=list,
        description=(
            "Optional SUN overlays. One LightRecipe(type='SUN', ...) is emitted per "
            "entry. Presets may supply a single dict, normalized to a one-element list."
        ),
    )

    @field_validator("directional", mode="before")
    @classmethod
    def _wrap_singleton(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, (dict, DirectionalLightConfig)):
            return [v]
        return v

    @model_validator(mode="after")
    def validate_ranges(self) -> "LightingConfig":
        """Ensure minimum values do not exceed maximum values."""
        if self.intensity_min > self.intensity_max:
            raise ValueError("intensity_min must be <= intensity_max")
        if self.radius_min > self.radius_max:
            raise ValueError("radius_min must be <= radius_max")
        return self


class SceneConfig(BaseModel):
    """Scene configuration."""

    lighting: LightingConfig = Field(
        default_factory=LightingConfig, description="Lighting parameters"
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
        """Ensure min scale <= max scale."""
        if self.texture_scale_min > self.texture_scale_max:
            raise ValueError("texture_scale_min must be <= texture_scale_max")
        return self


class PhysicsConfig(BaseModel):
    """Physics simulation configuration."""

    drop_height: float = Field(default=0.2, ge=0, description="Drop height in meters")
    scatter_radius: float = Field(default=0.5, gt=0, description="Scatter radius in meters")


class ScenarioConfig(BaseModel):
    """Configuration for a generation scenario.

    Defines the subject (Tags or Board) and environmental constraints.
    """

    model_config = ConfigDict(extra="forbid")

    subject: SubjectConfig | None = Field(
        default_factory=lambda: SubjectConfig(root=TagSubjectConfig()),
        description="The subject of the scene (TAGS or BOARD).",
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
    tag_spacing_bits: float = Field(
        default=2.0,
        description="Spacing between tags in number of bits (relative to tag grid size)",
    )


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

    version: str = Field(default=CURRENT_SCHEMA_VERSION, description="Schema version")
    presets: list[str] = Field(
        default_factory=list,
        description=(
            "Names of presets applied by the ACL in composition order. "
            "Informational on a validated config; set by `presets: [...]` in YAML "
            "and/or `--preset NAME` on the CLI."
        ),
    )
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    tag: TagConfig = Field(default_factory=TagConfig)
    scene: SceneConfig = Field(default_factory=SceneConfig)
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    scenario: ScenarioConfig = Field(default_factory=ScenarioConfig)
    renderer: RendererConfig = Field(default_factory=RendererConfig)
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

    # Anti-Corruption Layer: Translate legacy formats to modern schema.
    # The migrated payload is kept in memory only — use `render-tag config migrate --write`
    # to rewrite the file on disk.
    from render_tag.core.schema_adapter import adapt_config

    data = adapt_config(data)

    return GenConfig.model_validate(data)
