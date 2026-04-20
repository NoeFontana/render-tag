"""
Rigid schema for render-tag Scene Recipes.

Following the "Move-Left" architecture, this schema defines exactly what
a worker needs to render a single frame, with all random decisions resolved.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .board import BoardConfig
from .renderer import RendererConfig


class SensorNoiseComponent(BaseModel):
    """Single noise layer in a stacked sensor-noise pipeline."""

    model: str = Field(default="gaussian")
    mean: float = Field(default=0.0)
    stddev: float = Field(default=0.0, ge=0.0)
    salt_vs_pepper: float = Field(default=0.5, ge=0.0, le=1.0)
    amount: float = Field(default=0.0, ge=0.0, le=1.0)
    scale: float = Field(
        default=1000.0,
        gt=0.0,
        description="Poisson scale factor (photon count per unit intensity).",
    )
    seed: int | None = Field(
        default=None,
        description="Per-component seed. If None, derived from the parent config's seed.",
    )


class SensorNoiseConfig(BaseModel):
    """Configuration for parametric sensor noise.

    Backward-compatible: flat fields describe a single-model pipeline (legacy
    shape). ``models`` opts into a stacked pipeline where each component is
    applied in list order — real sensors stack shot + read + quantization
    noise, and this field lets the schema express that honestly.

    If both are present, ``models`` wins and the flat fields are ignored.
    """

    model: str = Field(default="gaussian")
    mean: float = Field(default=0.0)
    stddev: float = Field(default=0.0, ge=0.0)
    salt_vs_pepper: float = Field(default=0.5, ge=0.0, le=1.0)
    amount: float = Field(default=0.0, ge=0.0, le=1.0)
    scale: float = Field(
        default=1000.0,
        gt=0.0,
        description="Poisson scale factor (photon count per unit intensity).",
    )
    seed: int | None = Field(default=None, description="Deterministic noise seed")
    models: list[SensorNoiseComponent] | None = Field(
        default=None,
        description="Stacked noise layers applied in order. Overrides flat fields when set.",
    )


class SensorDynamicsRecipe(BaseModel):
    """Recipe for dynamic sensor artifacts (Motion Blur, Rolling Shutter)."""

    velocity: list[float] | None = Field(
        default=None, description="[vx, vy, vz] velocity vector in m/s"
    )
    shutter_time_ms: float | None = None
    rolling_shutter_duration_ms: float | None = None


class CameraIntrinsics(BaseModel):
    """Camera intrinsic parameters (baked into final K-matrix)."""

    resolution: list[int] = Field(
        min_length=2, max_length=2, description="[width, height] in pixels"
    )
    k_matrix: list[list[float]] = Field(
        description=(
            "3x3 Intrinsic matrix [[fx, 0, cx], [0, fy, cy], [0, 0, 1]] — "
            "TARGET distorted camera (used by PnP solvers on output images)"
        )
    )
    fov: float | None = Field(default=None, description="Field of view in degrees")

    # Lens distortion model
    distortion_model: Literal["none", "brown_conrady", "kannala_brandt"] = Field(
        default="none",
        description=(
            "Distortion model: 'none' (pinhole), 'brown_conrady' (5-param radial+tangential),"
            " or 'kannala_brandt' (4-param equidistant fisheye)"
        ),
    )
    distortion_coeffs: list[float] = Field(
        default_factory=list,
        description=(
            "Distortion coefficients: [k1,k2,p1,p2,k3] for brown_conrady;"
            " [k1,k2,k3,k4] for kannala_brandt"
        ),
    )

    # Overscan render targets — set by compiler when distortion is active.
    # None means no distortion; use k_matrix / resolution directly for Blender.
    k_matrix_overscan: list[list[float]] | None = Field(
        default=None,
        description="Expanded K-matrix for linear overscan render passed to Blender",
    )
    resolution_overscan: list[int] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Expanded [width, height] for linear overscan render passed to Blender",
    )

    # Spherical overscan render targets — set by compiler for kannala_brandt.
    # Mutually exclusive with k_matrix_overscan/resolution_overscan (linear path).
    fov_spherical: float | None = Field(
        default=None,
        description="Full FOV in radians for Blender FISHEYE_EQUIDISTANT camera",
    )
    resolution_spherical: list[int] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="[R, R] square resolution for equidistant intermediate render",
    )

    # Evaluation Margin ("Don't Care" Zone)
    eval_margin_px: int = Field(
        default=0,
        ge=0,
        description=(
            "Pixel-width margin along image edges treated as a 'Don't Care' zone. "
            "Keypoints within this margin receive v=1 (labeled but not visible) in "
            "COCO export instead of v=2. "
            "Typical value: 5px (half-radius of a standard 11-px Gaussian kernel)."
        ),
    )


class CameraRecipe(BaseModel):
    """Recipe for a camera pose and configuration."""

    transform_matrix: list[list[float]] = Field(
        description="4x4 Camera-to-World transformation matrix"
    )
    intrinsics: CameraIntrinsics
    sensor_dynamics: SensorDynamicsRecipe | None = None
    fstop: float | None = None
    focus_distance: float | None = None
    min_tag_pixels: int | None = Field(
        default=None, description="Minimum visible tag area in pixels"
    )
    max_tag_pixels: int | None = Field(
        default=None, description="Maximum visible tag area in pixels"
    )
    iso_noise: float | None = None
    sensor_noise: SensorNoiseConfig | None = None
    tone_mapping: Literal["linear", "srgb", "filmic"] = Field(
        default="filmic",
        description="Post-render tone-mapping operator applied before sensor noise.",
    )
    dynamic_range_db: float | None = Field(
        default=None,
        description="Sensor dynamic range in dB. None disables DR clipping.",
    )


class ObjectRecipe(BaseModel):
    """Recipe for a single object in the scene."""

    type: str = Field(description="Object type: TAG, BOARD, PLANE, etc.")
    name: str = Field(description="Unique name for the object")
    location: list[float] = Field(min_length=3, max_length=3)
    rotation_euler: list[float] | None = Field(default=None, min_length=3, max_length=3)
    rotation_quaternion: list[float] | None = Field(
        default=None, min_length=4, max_length=4, description="[w, x, y, z]"
    )
    scale: list[float] = Field(default=[1.0, 1.0, 1.0])
    properties: dict[str, Any] = Field(default_factory=dict)
    material: dict[str, Any] | None = None
    texture_path: str | None = None
    board: BoardConfig | None = None
    forward_axis: list[float] | None = Field(
        default=None, min_length=4, max_length=4, description="Local forward vector [x, y, z, 0]"
    )
    keypoints_3d: list[list[float]] | None = Field(
        default=None, description="Standardized 3D keypoints [x, y, z] in local object space"
    )
    calibration_points_3d: list[list[float]] | None = Field(
        default=None,
        description="Optional grid of points (e.g., ChArUco saddle points) in local object space",
    )


class LightRecipe(BaseModel):
    """Specific light source configuration."""

    type: Literal["POINT", "SUN"] = "POINT"
    location: list[float]
    intensity: float
    radius: float = 0.0
    color: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    rotation_euler: list[float] | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description=(
            "XYZ-Euler rotation in radians. Required for SUN lights to control "
            "direction; ignored for POINT."
        ),
    )


class WorldRecipe(BaseModel):
    """Resolved world environment configuration."""

    background_hdri: str | None = None
    hdri_rotation: float = 0.0

    # Explicit lights (Move-Left: Host decides positions)
    lights: list[LightRecipe] = Field(default_factory=list)

    # Background Texture Plane
    texture_path: str | None = None
    texture_scale: float = 1.0
    texture_rotation: float = 0.0


class SceneRecipe(BaseModel):
    """Complete instruction set for a single generated scene."""

    model_config = ConfigDict(extra="forbid")

    scene_id: int = Field(description="Unique ID for this scene")
    random_seed: int = Field(description="Resolved seed for this scene")
    world: WorldRecipe = Field(default_factory=WorldRecipe)
    renderer: RendererConfig = Field(default_factory=RendererConfig)
    objects: list[ObjectRecipe] = Field(default_factory=list)
    cameras: list[CameraRecipe] = Field(default_factory=list)
