"""
Rigid schema for render-tag Scene Recipes.

Following the "Move-Left" architecture, this schema defines exactly what
a worker needs to render a single frame, with all random decisions resolved.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .renderer import RendererConfig
from .board import BoardConfig


class SensorNoiseConfig(BaseModel):
    """Configuration for parametric sensor noise."""

    model: str = Field(default="gaussian")
    mean: float = Field(default=0.0)
    stddev: float = Field(default=0.0, ge=0.0)
    salt_vs_pepper: float = Field(default=0.5, ge=0.0, le=1.0)
    amount: float = Field(default=0.0, ge=0.0, le=1.0)
    seed: int | None = Field(default=None, description="Deterministic noise seed")


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
        description="3x3 Intrinsic matrix [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]"
    )
    fov: float | None = Field(default=None, description="Field of view in degrees")


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
    board: Optional[BoardConfig] = None
    keypoints_3d: list[list[float]] | None = Field(
        default=None, description="Standardized 3D keypoints [x, y, z] in local object space"
    )


class LightRecipe(BaseModel):
    """Specific light source configuration."""

    type: Literal["POINT", "SUN"] = "POINT"
    location: list[float]
    intensity: float
    radius: float = 0.0
    color: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])


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
