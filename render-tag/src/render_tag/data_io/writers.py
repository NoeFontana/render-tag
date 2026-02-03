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
from typing import TYPE_CHECKING, ClassVar

import numpy as np

if TYPE_CHECKING:
    pass


# Import pure-Python geometry modules
try:
    import sys
    from pathlib import Path

    pkg_root = Path(__file__).parent.parent
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))
    from render_tag.data_io.annotations import compute_bbox, normalize_corner_order
    from render_tag.geometry.math import compute_polygon_area

    GEOMETRY_AVAILABLE = True
except ImportError:
    GEOMETRY_AVAILABLE = False


from .types import DetectionRecord


class CSVWriter:
    """Writes detection data to a CSV file."""

    HEADER: ClassVar[list[str]] = [
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

        # Delegate CSV formatting to the data record
        row = detection.to_csv_row(width=width, height=height)

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
        width: int | None = None,
        height: int | None = None,
        detection: DetectionRecord | None = None,
    ) -> int:
        """Add an annotation for a detected tag (optionally clipped)."""
        if corners is None and detection is not None:
            corners = detection.corners

        if corners is None or len(corners) != 4:
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

        # Prepare attributes
        attributes = {
            "tag_id": detection.tag_id if detection else 0,
            "distance": detection.distance if detection else 0.0,
            "angle_of_incidence": detection.angle_of_incidence if detection else 0.0,
            "pixel_area": detection.pixel_area if detection else area,
            "occlusion_ratio": detection.occlusion_ratio if detection else 0.0,
        }
        if detection and hasattr(detection, "metadata"):
            attributes.update(detection.metadata)

        self.annotations.append(
            {
                "id": annotation_id,
                "image_id": image_id,
                "category_id": category_id,
                "segmentation": [segmentation],
                "bbox": bbox,
                "area": area,
                "iscrowd": 0,
                "attributes": attributes,
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


class RichTruthWriter:
    """Writer for structured JSON 'Data Product' containing all metadata."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self._detections: list[dict] = []

    def add_detection(self, detection: DetectionRecord) -> None:
        """Add a detection record to the output list."""
        # Convert dataclass to dict, handle simple types
        record = {
            "image_id": detection.image_id,
            "tag_id": detection.tag_id,
            "tag_family": detection.tag_family,
            "corners": detection.corners,
            "distance": detection.distance,
            "angle_of_incidence": detection.angle_of_incidence,
            "pixel_area": detection.pixel_area,
            "occlusion_ratio": detection.occlusion_ratio,
            "metadata": detection.metadata,
        }
        self._detections.append(record)

    def save(self) -> Path:
        """Save all detections to the JSON file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            json.dump(self._detections, f, indent=2)
        return self.output_path
