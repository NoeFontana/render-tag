"""
Output data schemas for render-tag synthetic data generation.

These schemas define the contracts for detection outputs and annotations.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Corner:
    """A 2D corner point in image coordinates."""

    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class TagDetection:
    """Detection output for a single fiducial marker (AprilTag or ArUco).

    Corner order follows Counter-Clockwise convention starting from Bottom-Left:
    BL (0), BR (1), TR (2), TL (3)

    This matches the Locus detector CSV format.
    """

    image_id: str
    tag_id: int
    tag_family: str = ""  # Optional: tag family identifier
    corners: list[Corner] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.corners) != 0 and len(self.corners) != 4:
            raise ValueError(f"TagDetection must have exactly 4 corners, got {len(self.corners)}")

    def to_csv_row(self) -> list[str | int | float]:
        """Convert to CSV row format: image_id, tag_id, tag_family, x1, y1, x2, y2, x3, y3, x4, y4."""
        row: list[str | int | float] = [self.image_id, self.tag_id, self.tag_family]
        for corner in self.corners:
            row.extend([corner.x, corner.y])
        return row

    @staticmethod
    def csv_header() -> list[str]:
        """Return CSV header row."""
        return ["image_id", "tag_id", "tag_family", "x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"]


@dataclass
class COCOImage:
    """COCO format image metadata."""

    id: int
    file_name: str
    width: int
    height: int


@dataclass
class COCOCategory:
    """COCO format category."""

    id: int
    name: str
    supercategory: str = "fiducial_marker"  # Covers both AprilTag and ArUco


@dataclass
class COCOAnnotation:
    """COCO format annotation for instance segmentation.

    Follows the standard COCO annotation format for compatibility
    with ML frameworks expecting COCO-style datasets.
    """

    id: int
    image_id: int
    category_id: int
    segmentation: list[list[float]] = field(default_factory=list)  # Polygon vertices
    bbox: list[float] = field(default_factory=list)  # [x, y, width, height]
    area: float = 0.0
    iscrowd: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to COCO JSON format."""
        return {
            "id": self.id,
            "image_id": self.image_id,
            "category_id": self.category_id,
            "segmentation": self.segmentation,
            "bbox": self.bbox,
            "area": self.area,
            "iscrowd": self.iscrowd,
        }


@dataclass
class COCODataset:
    """Complete COCO format dataset."""

    images: list[COCOImage] = field(default_factory=list)
    annotations: list[COCOAnnotation] = field(default_factory=list)
    categories: list[COCOCategory] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to COCO JSON format."""
        return {
            "images": [
                {"id": img.id, "file_name": img.file_name, "width": img.width, "height": img.height}
                for img in self.images
            ],
            "annotations": [ann.to_dict() for ann in self.annotations],
            "categories": [
                {"id": cat.id, "name": cat.name, "supercategory": cat.supercategory} for cat in self.categories
            ],
        }
