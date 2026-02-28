"""
Schema for render-tag Scene Recipes.

This module defines strict contracts for scene data generation using Pydantic.
This ensures that the "Generator" (Python logic) produces valid, typed data
that the "Executor" (Blender) or "Shadow Renderer" (Visualization) can consume safely.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TagFamily(str, Enum):
    """Fiducial tag families."""

    TAG36H11 = "tag36h11"
    TAG36H10 = "tag36h10"
    TAG25H9 = "tag25h9"
    TAG16H5 = "tag16h5"
    TAGCIRCLE21H7 = "tagCircle21h7"
    TAGCIRCLE49H12 = "tagCircle49h12"
    TAGCUSTOM48H12 = "tagCustom48h12"
    TAGSTANDARD41H12 = "tagStandard41h12"
    TAGSTANDARD52H13 = "tagStandard52h13"
    DICT_4X4_50 = "DICT_4X4_50"
    DICT_4X4_100 = "DICT_4X4_100"
    DICT_4X4_250 = "DICT_4X4_250"
    DICT_6X6_1000 = "DICT_6X6_1000"
    DICT_7X7_50 = "DICT_7X7_50"
    DICT_7X7_100 = "DICT_7X7_100"
    DICT_7X7_250 = "DICT_7X7_250"
    DICT_7X7_1000 = "DICT_7X7_1000"
    DICT_ARUCO_ORIGINAL = "DICT_ARUCO_ORIGINAL"


class ObjectType(str, Enum):
    """Types of objects in the scene."""

    TAG = "TAG"
    BOARD = "BOARD"
    PLANE = "PLANE"
    DISTRACTOR = "DISTRACTOR"


class EvaluationScope(str, Enum):
    """Scopes for dataset evaluation."""

    DETECTION = "detection"
    POSE = "pose"
    SEGMENTATION = "segmentation"


class NoiseType(str, Enum):
    """Types of sensor noise models."""

    GAUSSIAN = "gaussian"
    POISSON = "poisson"
    SALT_AND_PEPPER = "salt_and_pepper"


# These models have been moved to .recipe for the "Move-Left" architecture.
# See src/render_tag/core/schema/recipe.py


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

    @field_validator("corners")
    @classmethod
    def validate_corners_contract(cls, v: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Verify that corners meet the strict geometric contract (CW winding)."""
        if len(v) != 4:
            return v  # Other logic (like saddles) might have different counts

        from render_tag.generation.projection_math import validate_winding_order

        if not validate_winding_order(v):
            raise ValueError(
                "Detection corners must follow a strictly Clockwise winding order "
                "(OpenCV Y-down convention)."
            )
        return v

    # Calibration & Keypoint Support
    record_type: str = Field(default="TAG", description="TAG, CHARUCO_SADDLE, or APRILGRID_CORNER")
    keypoints: list[tuple[float, float]] | None = Field(
        default=None, description="Optional extra keypoints (e.g. saddle points)"
    )

    # Phase 6: Rich Metadata
    distance: float = 0.0
    angle_of_incidence: float = 0.0
    pixel_area: float = 0.0
    occlusion_ratio: float = 0.0
    ppm: float = 0.0

    # Phase 2 Pose Baseline: High-Precision Pose
    position: list[float] | None = Field(default=None, description="[x, y, z] position in meters")
    rotation_quaternion: list[float] | None = Field(
        default=None, description="[w, x, y, z] quaternion (Scalar First)"
    )

    # Provenance
    global_seed: int | None = Field(default=None, description="Master random seed used")
    scene_seed: int | None = Field(default=None, description="Scene-specific derived seed")

    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if the detection is valid (has 4 corners)."""
        return len(self.corners) == 4

    def to_csv_row(
        self, width: float | None = None, height: float | None = None
    ) -> list[str | int | float]:
        """Convert to CSV row format (normalized and optionally clipped)."""
        from render_tag.data_io.annotations import normalize_corner_order

        row: list[str | int | float] = [
            self.image_id,
            self.tag_id,
            self.tag_family,
            self.record_type,
            float(f"{self.ppm:.4f}"),
        ]

        # CSV format uses standard CW order from TL (OpenCV convention)
        if len(self.corners) == 4:
            ordered_corners = normalize_corner_order(self.corners, target_order="cw_tl")
        else:
            ordered_corners = self.corners

        for x, y in ordered_corners:
            if width is not None:
                x = max(0.0, min(float(width), x))
            if height is not None:
                y = max(0.0, min(float(height), y))
            # Format to 4 decimal places for consistency
            row.extend([float(f"{x:.4f}"), float(f"{y:.4f}")])

        # Append extra keypoints if present
        if self.keypoints:
            for x, y in self.keypoints:
                if width is not None:
                    x = max(0.0, min(float(width), x))
                if height is not None:
                    y = max(0.0, min(float(height), y))
                row.extend([float(f"{x:.4f}"), float(f"{y:.4f}")])
        return row

    @staticmethod
    def csv_header(num_corners: int = 4, num_keypoints: int = 0) -> list[str]:
        """Return CSV header row for corner and keypoint annotations."""
        header = [
            "image_id",
            "tag_id",
            "tag_family",
            "record_type",
            "ppm",
        ]
        for i in range(1, num_corners + 1):
            header.extend([f"x{i}", f"y{i}"])
        for i in range(1, num_keypoints + 1):
            header.extend([f"kp{i}_x", f"kp{i}_y"])
        return header


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

    # Keypoints support
    keypoints: list[float] | None = Field(default=None, description="[x1, y1, v1, ...]")
    num_keypoints: int | None = Field(default=None)

    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard COCO JSON dictionary."""
        d = {
            "id": self.id,
            "image_id": self.image_id,
            "category_id": self.category_id,
            "segmentation": self.segmentation,
            "bbox": self.bbox,
            "area": self.area,
            "iscrowd": self.iscrowd,
            "attributes": self.attributes,
        }
        if self.keypoints is not None:
            d["keypoints"] = self.keypoints
            d["num_keypoints"] = self.num_keypoints
        return d
