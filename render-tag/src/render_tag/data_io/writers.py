"""
Data export writers for render-tag.

This module handles writing detection annotations in various formats:
- CSV format for corner coordinates (Locus-compatible)
- COCO format for instance segmentation
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Import pure-Python geometry modules
try:
    import sys
    from pathlib import Path

    pkg_root = Path(__file__).parent.parent
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))
    from render_tag.geometry.math import compute_polygon_area
    from render_tag.data_io.annotations import compute_bbox, normalize_corner_order

    GEOMETRY_AVAILABLE = True
except ImportError:
    GEOMETRY_AVAILABLE = False


from .types import DetectionRecord


class CSVWriter:
    """Writer for CSV format detection annotations.

    Format: image_id, tag_id, tag_family, x1, y1, x2, y2, x3, y3, x4, y4
    Corner order: BL (0), BR (1), TR (2), TL (3) - Counter-Clockwise from Bottom-Left
    """

    HEADER = [
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

    def __init__(self, output_path: Path) -> None:
        """Initialize the CSV writer."""
        self.output_path = output_path
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Create the file and write header if not already done."""
        if not self._initialized:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADER)
            self._initialized = True

    def write_detection(
        self,
        detection: DetectionRecord,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        """Write a single detection to the CSV file (optionally clipped)."""
        if not detection.validate():
            return

        self._ensure_initialized()

        # CSV format uses standard CCW order from BL
        ordered_corners = normalize_corner_order(
            detection.corners, target_order="ccw_bl"
        )

        # Clip if dimensions provided
        if width is not None or height is not None:
            ordered_corners = [
                (
                    max(0.0, min(float(width or 1e9), c[0])),
                    max(0.0, min(float(height or 1e9), c[1])),
                )
                for c in ordered_corners
            ]

        row = [detection.image_id, detection.tag_id, detection.tag_family]
        for corner in ordered_corners:
            row.extend([f"{corner[0]:.4f}", f"{corner[1]:.4f}"])

        with open(self.output_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def write_detections(self, detections: list[DetectionRecord]) -> None:
        """Write multiple detections to the CSV file."""
        for detection in detections:
            self.write_detection(detection)


class COCOWriter:
    """Writer for COCO format annotations."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize the COCO writer."""
        self.output_dir = output_dir
        self.images: list[dict] = []
        self.annotations: list[dict] = []
        self.categories: list[dict] = []
        self._category_map: dict[str, int] = {}
        self._next_image_id = 1
        self._next_annotation_id = 1

    def add_category(self, name: str, supercategory: str = "fiducial_marker") -> int:
        """Add a category and return its ID."""
        if name in self._category_map:
            return self._category_map[name]

        cat_id = len(self.categories) + 1
        self.categories.append(
            {
                "id": cat_id,
                "name": name,
                "supercategory": supercategory,
            }
        )
        self._category_map[name] = cat_id
        return cat_id

    def add_image(self, file_name: str, width: int, height: int) -> int:
        """Add an image entry and return its ID."""
        image_id = self._next_image_id
        self._next_image_id += 1

        self.images.append(
            {
                "id": image_id,
                "file_name": file_name,
                "width": width,
                "height": height,
            }
        )
        return image_id

    def add_annotation(
        self,
        image_id: int,
        category_id: int,
        corners: list[tuple[float, float]],
        tag_id: int = 0,
        width: int | None = None,
        height: int | None = None,
    ) -> int:
        """Add an annotation for a detected tag (optionally clipped)."""
        if len(corners) != 4:
            raise ValueError("Annotation must have exactly 4 corners")

        annotation_id = self._next_annotation_id
        self._next_annotation_id += 1

        # Clip corners if dimensions provided
        if width is not None or height is not None:
            corners = [
                (
                    max(0.0, min(float(width or 1e9), c[0])),
                    max(0.0, min(float(height or 1e9), c[1])),
                )
                for c in corners
            ]

        # 1. Use pure-Python utility for bbox
        bbox = compute_bbox(np.array(corners))

        # 2. Use pure-Python utility for area
        area = compute_polygon_area(np.array(corners))

        # 3. Use pure-Python utility for corner reordering (COCO prefers CW from TL)
        ordered_corners = normalize_corner_order(corners, target_order="cw_tl")
        segmentation = []
        for corner in ordered_corners:
            segmentation.extend([corner[0], corner[1]])

        self.annotations.append(
            {
                "id": annotation_id,
                "image_id": image_id,
                "category_id": category_id,
                "segmentation": [segmentation],
                "bbox": bbox,
                "area": area,
                "iscrowd": 0,
                "attributes": {"tag_id": tag_id},
            }
        )

        return annotation_id

    def save(self, filename: str = "annotations.json") -> Path:
        """Save the COCO annotations to a JSON file."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / filename

        coco_data = {
            "images": self.images,
            "annotations": self.annotations,
            "categories": self.categories,
        }

        with open(output_path, "w") as f:
            json.dump(coco_data, f, indent=2)

        return output_path


def corners_to_clockwise_order(
    corners: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Legacy helper maintained for backward compatibility."""
    return normalize_corner_order(corners, target_order="cw_tl")


def verify_corner_order(
    corners: list[tuple[float, float]],
    expected_order: str = "ccw",
) -> bool:
    """Verify that corners are in the expected winding order."""
    if len(corners) != 4:
        return False

    # We need signed area for winding order
    x = np.array([c[0] for c in corners])
    y = np.array([c[1] for c in corners])
    signed_area = 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    if expected_order == "ccw":
        return bool(signed_area > 0)
    else:  # cw
        return bool(signed_area < 0)
