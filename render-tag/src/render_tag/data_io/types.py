"""
Centralized type definitions for render-tag data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Corner:
    """A 2D corner point in image coordinates."""

    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        """Convert to (x, y) tuple."""
        return (self.x, self.y)


@dataclass
class DetectionRecord:
    """A single detection record for export and processing."""

    image_id: str
    tag_id: int
    tag_family: str
    corners: list[tuple[float, float]]  # Standardized as list of tuples

    def validate(self) -> bool:
        """Check if the detection is valid (has 4 corners)."""
        return len(self.corners) == 4

    def to_csv_row(
        self, width: float | None = None, height: float | None = None
    ) -> list[str | int | float]:
        """Convert to CSV row format (optionally clipped)."""
        row: list[str | int | float] = [self.image_id, self.tag_id, self.tag_family]
        for x, y in self.corners:
            if width is not None:
                x = max(0.0, min(float(width), x))
            if height is not None:
                y = max(0.0, min(float(height), y))
            row.extend([x, y])
        return row

    @staticmethod
    def csv_header() -> list[str]:
        """Return CSV header row matching Locus format."""
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
    supercategory: str = "fiducial_marker"


@dataclass
class COCOAnnotation:
    """COCO format annotation."""

    id: int
    image_id: int
    category_id: int
    segmentation: list[list[float]] = field(default_factory=list)
    bbox: list[float] = field(default_factory=list)
    area: float = 0.0
    iscrowd: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)

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
