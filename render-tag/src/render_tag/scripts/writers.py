"""
Data export writers for render-tag.

This module handles writing detection annotations in various formats:
- CSV format for corner coordinates (Locus-compatible)
- COCO format for instance segmentation
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    pass


@dataclass
class DetectionRecord:
    """A single detection record for export."""
    
    image_id: str
    tag_id: int
    tag_family: str
    corners: list[tuple[float, float]]  # 4 corners in CCW order: BL, BR, TR, TL
    
    def validate(self) -> bool:
        """Check if the detection is valid."""
        return len(self.corners) == 4


class CSVWriter:
    """Writer for CSV format detection annotations.
    
    Format: image_id, tag_id, tag_family, x1, y1, x2, y2, x3, y3, x4, y4
    Corner order: BL (0), BR (1), TR (2), TL (3) - Counter-Clockwise from Bottom-Left
    """
    
    HEADER = ["image_id", "tag_id", "tag_family", "x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"]
    
    def __init__(self, output_path: Path) -> None:
        """Initialize the CSV writer.
        
        Args:
            output_path: Path to the CSV file
        """
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
    
    def write_detection(self, detection: DetectionRecord) -> None:
        """Write a single detection to the CSV file.
        
        Args:
            detection: The detection record to write
        """
        if not detection.validate():
            return
        
        self._ensure_initialized()
        
        row = [detection.image_id, detection.tag_id, detection.tag_family]
        for corner in detection.corners:
            row.extend([f"{corner[0]:.4f}", f"{corner[1]:.4f}"])
        
        with open(self.output_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
    
    def write_detections(self, detections: list[DetectionRecord]) -> None:
        """Write multiple detections to the CSV file.
        
        Args:
            detections: List of detection records to write
        """
        for detection in detections:
            self.write_detection(detection)


class COCOWriter:
    """Writer for COCO format annotations.
    
    Generates instance segmentation annotations compatible with
    standard COCO dataset format.
    """
    
    def __init__(self, output_dir: Path) -> None:
        """Initialize the COCO writer.
        
        Args:
            output_dir: Directory to write the annotations.json file
        """
        self.output_dir = output_dir
        self.images: list[dict] = []
        self.annotations: list[dict] = []
        self.categories: list[dict] = []
        self._category_map: dict[str, int] = {}
        self._next_image_id = 1
        self._next_annotation_id = 1
    
    def add_category(self, name: str, supercategory: str = "fiducial_marker") -> int:
        """Add a category and return its ID.
        
        Args:
            name: Category name (e.g., "tag36h11")
            supercategory: Parent category
            
        Returns:
            Category ID
        """
        if name in self._category_map:
            return self._category_map[name]
        
        cat_id = len(self.categories) + 1
        self.categories.append({
            "id": cat_id,
            "name": name,
            "supercategory": supercategory,
        })
        self._category_map[name] = cat_id
        return cat_id
    
    def add_image(self, file_name: str, width: int, height: int) -> int:
        """Add an image entry and return its ID.
        
        Args:
            file_name: Image filename
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Image ID
        """
        image_id = self._next_image_id
        self._next_image_id += 1
        
        self.images.append({
            "id": image_id,
            "file_name": file_name,
            "width": width,
            "height": height,
        })
        return image_id
    
    def add_annotation(
        self,
        image_id: int,
        category_id: int,
        corners: list[tuple[float, float]],
        tag_id: int = 0,
    ) -> int:
        """Add an annotation for a detected tag.
        
        Args:
            image_id: ID of the image
            category_id: ID of the category
            corners: 4 corner coordinates (x, y)
            tag_id: The specific tag ID within the family
            
        Returns:
            Annotation ID
        """
        if len(corners) != 4:
            raise ValueError("Annotation must have exactly 4 corners")
        
        annotation_id = self._next_annotation_id
        self._next_annotation_id += 1
        
        # Compute bounding box [x, y, width, height]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
        
        # Compute area using shoelace formula
        area = 0.0
        n = len(corners)
        for i in range(n):
            j = (i + 1) % n
            area += corners[i][0] * corners[j][1]
            area -= corners[j][0] * corners[i][1]
        area = abs(area) / 2.0
        
        # Segmentation: flatten corners to [x1, y1, x2, y2, x3, y3, x4, y4]
        segmentation = []
        for corner in corners:
            segmentation.extend([corner[0], corner[1]])
        
        self.annotations.append({
            "id": annotation_id,
            "image_id": image_id,
            "category_id": category_id,
            "segmentation": [segmentation],  # List of polygons
            "bbox": bbox,
            "area": area,
            "iscrowd": 0,
            "attributes": {"tag_id": tag_id},
        })
        
        return annotation_id
    
    def save(self, filename: str = "annotations.json") -> Path:
        """Save the COCO annotations to a JSON file.
        
        Args:
            filename: Name of the output file
            
        Returns:
            Path to the saved file
        """
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
    """Ensure corners are in clockwise order starting from top-left.
    
    Input order (CCW from BL): BL(0), BR(1), TR(2), TL(3)
    Output order (CW from TL): TL(0), TR(1), BR(2), BL(3)
    
    Args:
        corners: List of 4 (x, y) corner coordinates in CCW order from BL
        
    Returns:
        Corners reordered to CW from TL: TL, TR, BR, BL
    """
    if len(corners) != 4:
        return corners
    
    # Input: BL(0), BR(1), TR(2), TL(3) [CCW from bottom-left]
    # Output: TL(0), TR(1), BR(2), BL(3) [CW from top-left]
    bl, br, tr, tl = corners[0], corners[1], corners[2], corners[3]
    return [tl, tr, br, bl]


def verify_corner_order(
    corners: list[tuple[float, float]],
    expected_order: str = "ccw",
) -> bool:
    """Verify that corners are in the expected winding order.
    
    Args:
        corners: List of 4 (x, y) corner coordinates
        expected_order: "cw" for clockwise, "ccw" for counter-clockwise
        
    Returns:
        True if corners are in the expected order
    """
    if len(corners) != 4:
        return False
    
    # Compute signed area using shoelace formula
    # Positive = CCW, Negative = CW
    area = 0.0
    n = len(corners)
    for i in range(n):
        j = (i + 1) % n
        area += corners[i][0] * corners[j][1]
        area -= corners[j][0] * corners[i][1]
    
    if expected_order == "ccw":
        return area > 0
    else:  # cw
        return area < 0
