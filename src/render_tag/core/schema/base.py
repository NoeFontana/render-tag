"""
Schema for render-tag Scene Recipes.

This module defines strict contracts for scene data generation using Pydantic.
This ensures that the "Generator" (Python logic) produces valid, typed data
that the "Executor" (Blender) or "Shadow Renderer" (Visualization) can consume safely.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from render_tag.core.schema.board import BoardDefinition


class TagFamily(str, Enum):
    """Supported fiducial marker families.

    Includes both AprilTag families and ArUco dictionaries.
    """

    # AprilTag families
    TAG36H11 = "tag36h11"
    TAG36H10 = "tag36h10"
    TAG25H9 = "tag25h9"
    TAG16H5 = "tag16h5"

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
    sequence: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional sequence metadata such as frame index, fps, trajectory style, "
            "and ground-truth timing semantics"
        ),
    )


# =============================================================================
# Export & Detection Types
# =============================================================================


KEYPOINT_SENTINEL: tuple[float, float] = (-1.0, -1.0)
"""Sentinel value for out-of-frame or behind-camera calibration keypoints.

Preserves index alignment so ``keypoints[i]`` always maps to ``charuco_id == i``.
"""


def is_sentinel_keypoint(x: float, y: float) -> bool:
    """Check if a keypoint coordinate pair is the out-of-frame sentinel."""
    return x == KEYPOINT_SENTINEL[0] and y == KEYPOINT_SENTINEL[1]


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

        # Skip validation if any corner is invalid (behind camera)
        import numpy as np

        if np.any(np.array(v) <= -999999.0):
            return v

        from render_tag.generation.projection_math import validate_winding_order

        if not validate_winding_order(v):
            raise ValueError(
                "Detection corners must follow a strictly Clockwise winding order "
                "(OpenCV Y-down convention)."
            )
        return v

    # Calibration & Keypoint Support
    record_type: str = Field(default="TAG", description="TAG, BOARD, or CHARUCO_SADDLE")
    keypoints: list[tuple[float, float]] | None = Field(
        default=None, description="Optional extra keypoints (e.g. saddle points)"
    )

    # Phase 6: Rich Metadata
    distance: float = 0.0
    angle_of_incidence: float = 0.0
    pixel_area: float = 0.0
    occlusion_ratio: float = 0.0
    ppm: float = 0.0

    is_mirrored: bool = Field(
        default=False, description="True if the tag has a left-handed (mirrored) coordinate system"
    )

    # --- Phase 2 Pose Baseline: High-Precision Pose ---
    position: list[float] | None = Field(
        default=None,
        description="[x, y, z] position in meters (OpenCV Frame), referenced at exposure midpoint",
    )
    rotation_quaternion: list[float] | None = Field(
        default=None,
        description=(
            "[w, x, y, z] quaternion (Internal Scalar-First), referenced at exposure midpoint"
        ),
    )
    axes: dict[str, list[tuple[float, float]]] | None = Field(
        default=None, description="Pre-computed 2D projections of the 3D X, Y, Z axes"
    )
    tag_size_mm: float = Field(
        default=0.0, description="Active physical size (black-to-black) in millimeters"
    )

    # --- Unified Data Product: Intrinsics ---
    k_matrix: list[list[float]] | None = Field(
        default=None, description="3x3 Camera Intrinsic Matrix [[fx, 0, cx], ...]"
    )
    resolution: list[int] | None = Field(default=None, description="[width, height] in pixels")

    # --- Unified Data Product: Physics & Sensor Conditions ---
    velocity: list[float] | None = Field(
        default=None, description="Camera velocity [vx, vy, vz] in m/s"
    )
    shutter_time_ms: float = Field(
        default=0.0,
        description="Exposure time in milliseconds; pose/corners are defined at exposure midpoint",
    )
    rolling_shutter_ms: float = Field(
        default=0.0, description="Rolling shutter scan duration in milliseconds"
    )
    fstop: float | None = Field(default=None, description="Aperture f-number")

    # --- Provenance ---
    global_seed: int | None = Field(default=None, description="Master random seed used")
    scene_seed: int | None = Field(default=None, description="Scene-specific derived seed")

    metadata: dict[str, Any] = Field(default_factory=dict)

    # --- Board Topology (BOARD records only) ---
    board_definition: BoardDefinition | None = Field(
        default=None, description="Resolved board geometry for BOARD records"
    )

    def is_valid(self) -> bool:
        """Check if the detection is valid (has 4 corners)."""
        return len(self.corners) == 4

    def to_csv_row(
        self, width: float | None = None, height: float | None = None
    ) -> list[str | int | float]:
        """Convert to CSV row format (normalized and optionally clipped)."""
        row: list[str | int | float] = [
            self.image_id,
            self.tag_id,
            self.tag_family,
            self.record_type,
            float(f"{self.tag_size_mm:.4f}"),
            float(f"{self.ppm:.4f}"),
            int(self.is_mirrored),
        ]

        # CSV format: corners are guaranteed CW from TL by the 3D asset contract.
        ordered_corners = self.corners

        for x, y in ordered_corners:
            if width is not None and x > -999999.0:
                x = max(0.0, min(float(width), x))
            if height is not None and y > -999999.0:
                y = max(0.0, min(float(height), y))
            # Format to 4 decimal places for consistency
            row.extend([float(f"{x:.4f}"), float(f"{y:.4f}")])

        # Append extra keypoints if present
        if self.keypoints:
            for x, y in self.keypoints:
                if is_sentinel_keypoint(x, y):
                    row.extend([-1.0, -1.0])
                    continue
                if width is not None and x > -999999.0:
                    x = max(0.0, min(float(width), x))
                if height is not None and y > -999999.0:
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
            "tag_size_mm",
            "ppm",
            "is_mirrored",
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
