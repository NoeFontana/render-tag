"""
Schema for render-tag Scene Recipes.

This module defines strict contracts for scene data generation using Pydantic.
This ensures that the "Generator" (Python logic) produces valid, typed data
that the "Executor" (Blender) or "Shadow Renderer" (Visualization) can consume safely.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NoiseType(str, Enum):
    """Types of sensor noise models."""

    GAUSSIAN = "gaussian"
    POISSON = "poisson"
    SALT_AND_PEPPER = "salt_and_pepper"


class SensorNoiseConfig(BaseModel):
    """Configuration for parametric sensor noise."""

    model: NoiseType = Field(default=NoiseType.GAUSSIAN, description="Noise model type")

    # Gaussian parameters
    mean: float = Field(default=0.0, description="Mean for Gaussian noise")
    stddev: float = Field(default=0.0, description="Standard deviation for Gaussian noise")

    # Salt and Pepper parameters
    salt_vs_pepper: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Probability of salt vs pepper"
    )
    amount: float = Field(default=0.0, ge=0.0, le=1.0, description="Proportion of pixels to affect")


class SensorDynamicsRecipe(BaseModel):
    """Recipe for dynamic sensor artifacts (Motion Blur, Rolling Shutter)."""

    velocity: list[float] | None = Field(
        default=None, description="[vx, vy, vz] velocity vector in m/s"
    )
    shutter_time_ms: float | None = Field(default=None, description="Shutter time in ms")
    rolling_shutter_duration_ms: float | None = Field(
        default=None, description="Rolling shutter duration in ms"
    )


class TagSurfaceConfig(BaseModel):
    """Configuration for tag surface imperfections."""

    scratches: float = Field(default=0.0, ge=0.0, le=1.0, description="Intensity of scratches")
    dust: float = Field(default=0.0, ge=0.0, le=1.0, description="Intensity of dust")
    grunge: float = Field(default=0.0, ge=0.0, le=1.0, description="Intensity of grunge/stains")


class ObjectRecipe(BaseModel):
    """Recipe for a single object in the scene."""

    type: str = Field(description="Object type: TAG, BOARD, PLANE, etc.")
    name: str = Field(description="Unique name for the object")
    location: list[float] = Field(
        min_length=3, max_length=3, description="[x, y, z] location in meters"
    )
    rotation_euler: list[float] = Field(
        min_length=3, max_length=3, description="[x, y, z] euler rotation in radians"
    )
    scale: list[float] = Field(default=[1.0, 1.0, 1.0], min_length=3, max_length=3)
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Custom properties: tag_id, family, etc."
    )
    material: str | None = None
    texture_path: str | None = None


class CameraIntrinsics(BaseModel):
    """Camera intrinsic parameters."""

    resolution: list[int] = Field(
        min_length=2, max_length=2, description="[width, height] in pixels"
    )
    fov: float = Field(default=60.0, description="Horizontal field of view in degrees")
    intrinsics: dict[str, Any] = Field(
        default_factory=dict, description="Explicit K matrix or focal lengths"
    )


class CameraRecipe(BaseModel):
    """Recipe for a camera pose and configuration."""

    transform_matrix: list[list[float]] = Field(
        description="4x4 Camera-to-World transformation matrix"
    )
    intrinsics: CameraIntrinsics

    # Sensor Dynamics (Motion Blur, Rolling Shutter)
    sensor_dynamics: SensorDynamicsRecipe | None = Field(
        default=None, description="Dynamic sensor artifacts recipe"
    )

    # Depth of Field
    fstop: float | None = Field(default=None, description="Aperture f-stop")
    focus_distance: float | None = Field(default=None, description="Focus distance in meters")
    iso_noise: float | None = Field(default=None, description="ISO noise level (0-1)")
    sensor_noise: SensorNoiseConfig | None = Field(
        default=None, description="Parametric sensor noise config"
    )


class LightingConfig(BaseModel):
    """Lighting configuration for the scene."""

    intensity: float = Field(default=100.0, description="Light intensity/strength")
    color: list[float] = Field(default=[1.0, 1.0, 1.0], min_length=3, max_length=3)
    radius: float = Field(default=0.0, description="Light source radius (shadow softness)")


class WorldRecipe(BaseModel):
    """World environment configuration."""

    background_hdri: str | None = Field(default=None, description="Path to HDRI file")
    lighting: LightingConfig = Field(default_factory=LightingConfig)

    # Resolved Texture Parameters
    texture_path: str | None = Field(default=None, description="Path to chosen background texture")
    texture_scale: float = Field(default=1.0, description="Tiling scale for the texture")
    texture_rotation: float = Field(default=0.0, description="Rotation for the texture (radians)")

    use_nodes: bool = True


class SceneRecipe(BaseModel):
    """Complete recipe for a single generated scene."""

    model_config = ConfigDict(extra="forbid")

    scene_id: int = Field(description="Unique ID for this scene")
    world: WorldRecipe = Field(default_factory=WorldRecipe)
    objects: list[ObjectRecipe] = Field(default_factory=list)
    cameras: list[CameraRecipe] = Field(default_factory=list)


class SceneProvenance(BaseModel):
    """Metadata provenance for a generated image."""

    git_hash: str = Field(description="Git commit hash of the code used for generation")
    timestamp: str = Field(description="ISO 8601 timestamp of generation")
    recipe_snapshot: dict[str, Any] = Field(description="Snapshot of the SceneRecipe used")
    seeds: dict[str, int] | None = Field(default=None, description="Random seeds used")


# =============================================================================
# Export & Detection Types
# =============================================================================


class Corner(BaseModel):
    """A 2D corner point in image coordinates."""

    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        """Convert to (x, y) tuple."""
        return (self.x, self.y)


class DetectionRecord(BaseModel):
    """A single detection record for export and processing."""

    image_id: str
    tag_id: int
    tag_family: str
    corners: list[tuple[float, float]]  # Standardized as list of tuples

    # Phase 6: Rich Metadata
    distance: float = 0.0
    angle_of_incidence: float = 0.0
    pixel_area: float = 0.0
    occlusion_ratio: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if the detection is valid (has 4 corners)."""
        return len(self.corners) == 4

    def to_csv_row(
        self, width: float | None = None, height: float | None = None
    ) -> list[str | int | float]:
        """Convert to CSV row format (normalized and optionally clipped)."""
        from render_tag.data_io.annotations import normalize_corner_order

        row: list[str | int | float] = [self.image_id, self.tag_id, self.tag_family]

        # CSV format uses standard CCW order from BL
        ordered_corners = normalize_corner_order(self.corners, target_order="ccw_bl")

        for x, y in ordered_corners:
            if width is not None:
                x = max(0.0, min(float(width), x))
            if height is not None:
                y = max(0.0, min(float(height), y))
            # Format to 4 decimal places for consistency
            row.extend([float(f"{x:.4f}"), float(f"{y:.4f}")])
        return row

    @staticmethod
    def csv_header() -> list[str]:
        """Return CSV header row for corner annotations."""
        return [
            "image_id",
            "tag_id",
            "tag_family",
            "x1",
            "y1",
            "x2",
            "y2",
            "x3",
            "y3",
            "x4",
            "y4",
        ]


class COCOImage(BaseModel):
    """COCO format image metadata."""

    id: int
    file_name: str
    width: int
    height: int


class COCOCategory(BaseModel):
    """COCO format category."""

    id: int
    name: str
    supercategory: str = "fiducial_marker"


class COCOAnnotation(BaseModel):
    """COCO format annotation."""

    id: int
    image_id: int
    category_id: int
    segmentation: list[list[float]] = Field(default_factory=list)
    bbox: list[float] = Field(default_factory=list)
    area: float = 0.0
    iscrowd: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard COCO JSON dictionary."""
        return {
            "id": self.id,
            "image_id": self.image_id,
            "category_id": self.category_id,
            "segmentation": self.segmentation,
            "bbox": self.bbox,
            "area": self.area,
            "iscrowd": self.iscrowd,
            "attributes": self.attributes,
        }
