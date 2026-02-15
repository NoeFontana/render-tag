"""
Data export writers for render-tag.

This module handles writing detection annotations in various formats:
- CSV format for corner coordinates
- COCO format for instance segmentation
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from render_tag.core.schema import DetectionRecord

logger = logging.getLogger(__name__)


# Import pure-Python geometry modules
try:
    from render_tag.data_io.annotations import (
        compute_bbox,
        format_coco_keypoints,
        normalize_corner_order,
    )
    from render_tag.generation.math import compute_polygon_area

    GEOMETRY_AVAILABLE = True
except ImportError:
    GEOMETRY_AVAILABLE = False


if TYPE_CHECKING:
    from render_tag.core.schema import DetectionRecord, SceneProvenance


class CSVWriter:
    """Writes detection data to a CSV file."""

    HEADER: ClassVar[list[str]] = [
        "image_id",
        "tag_id",
        "tag_family",
        "ppm",
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
        if not detection.is_valid():
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

    def __init__(self, output_dir: Path, filename: str = "annotations.json") -> None:
        """Initialize the COCO writer."""
        self.output_dir = output_dir
        self.filename = filename
        self.images: list[dict] = []
        self.annotations: list[dict] = []
        self.categories: list[dict] = []
        self._category_map: dict[str, int] = {}
        self._next_image_id = 1
        self._next_annotation_id = 1
        self._dirty = False

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
                "keypoints": [
                    "bl",
                    "br",
                    "tr",
                    "tl",
                ],  # Standard corner names (CCW from BL default)
                "skeleton": [[1, 2], [2, 3], [3, 4], [4, 1]],  # Edges
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
        self._dirty = True
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
        # Note: normalize_corner_order returns [(x, y), ...]
        # We need to keep consistency. If we define keypoints as [bl, br, tr, tl] (CCW),
        # we should provide them in that order.
        # But 'segmentation' usually follows the polygon boundary.

        # Let's keep segmentation as CW from TL (standard COCO poly),
        # BUT keypoints should match the category definition.
        # If category says ["bl", "br", "tr", "tl"], we must provide them in that order.
        # Input 'corners' is assumed to be CCW from BL (standard render-tag/OpenCV output).

        # Segmentation:
        ordered_corners_seg = normalize_corner_order(corners, target_order="cw_tl")
        segmentation = []
        for corner in ordered_corners_seg:
            segmentation.extend([corner[0], corner[1]])

        # Keypoints:
        # Assuming input 'corners' is [BL, BR, TR, TL]
        # We want to format them as keypoints.
        # If we didn't reorder for segmentation, we'd use 'corners' directly for keypoints.
        # Let's ensure 'corners' is normalized to what our category expects.
        # Our category expects [bl, br, tr, tl].
        ordered_corners_kp = normalize_corner_order(corners, target_order="ccw_bl")
        keypoints = format_coco_keypoints(np.array(ordered_corners_kp))

        # Prepare attributes
        attributes = {
            "tag_id": detection.tag_id if detection else 0,
            "distance": detection.distance if detection else 0.0,
            "angle_of_incidence": detection.angle_of_incidence if detection else 0.0,
            "pixel_area": detection.pixel_area if detection else area,
            "occlusion_ratio": detection.occlusion_ratio if detection else 0.0,
            "position": detection.position if detection else None,
            "rotation_quaternion": None,
        }

        # IO BOUNDARY: Flip WXYZ -> XYZW for attributes
        if detection and detection.rotation_quaternion:
            w, x, y, z = detection.rotation_quaternion
            attributes["rotation_quaternion"] = [x, y, z, w]
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
                "keypoints": keypoints,
                "num_keypoints": 4,
                "iscrowd": 0,
                "attributes": attributes,
            }
        )
        self._dirty = True

        return annotation_id

    def save(self, filename: str | None = None) -> Path:
        """Save the COCO annotations to a JSON file."""
        if filename is None:
            filename = self.filename

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / filename
        logger.info(
            "Saving COCO annotations to %s (%d images, %d annotations)",
            output_path,
            len(self.images),
            len(self.annotations),
        )

        if not self._dirty:
            logger.debug("COCOWriter: No new annotations, skipping save")
            return output_path

        coco_data = {
            "images": self.images,
            "annotations": self.annotations,
            "categories": self.categories,
        }

        with open(output_path, "w") as f:
            json.dump(coco_data, f, indent=2)

        self._dirty = False
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
            "ppm": detection.ppm,
            "position": detection.position,
            "rotation_quaternion": detection.rotation_quaternion,
            "metadata": detection.metadata,
        }

        # IO BOUNDARY: Flip quaternion from WXYZ (Blender/internal) to XYZW (SciPy/Rust)
        if record["rotation_quaternion"] and len(record["rotation_quaternion"]) == 4:
            w, x, y, z = record["rotation_quaternion"]
            record["rotation_quaternion"] = [x, y, z, w]

        self._detections.append(record)

    def save(self) -> Path:
        """Save all detections to the JSON file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            json.dump(self._detections, f, indent=2)
        return self.output_path


class SidecarWriter:
    """Writes metadata sidecar files for generated images."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def write_sidecar(self, image_name: str, provenance: dict[str, Any] | SceneProvenance) -> Path:
        """Write the provenance data to a JSON sidecar file.

        Args:
            image_name: Base name of the image (e.g. 'scene_0000_cam_0000')
            provenance: SceneProvenance object or dict

        Returns:
            Path to the written file
        """
        # Place sidecar alongside images in 'images' subdirectory
        sidecar_dir = self.output_dir / "images"
        sidecar_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{image_name}_meta.json"
        path = sidecar_dir / filename

        # IO BOUNDARY: Ensure quaternion flip if checking tags in provenance
        # Typically the SceneProvenance might not have detailed detections,
        # but if we add them, we must ensure consistency.
        # Currently SceneProvenance creates a unique snapshot.

        # If we had detection records here, we'd flip them.
        # But SidecarWriter mostly writes the SceneProvenance/Recipe.
        # "Recipe" has camera positions which are matrices.
        # If we serialize specific geometric metadata here, we should check.
        # Current usage:
        # It dumps SceneProvenance which has `recipe_snapshot`.

        # If we have detection-level metadata for sidecars (which we might in later phases),
        # we'd process it here.
        # For now, we act on the user's instruction
        # "Implement the permutation logic strictly at the IO boundary inside writers.py".
        # RichTruthWriter is the main consumer of DetectionRecord.

        # We also have COCOWriter attributes.

        with open(path, "w") as f:
            if isinstance(provenance, dict):
                json.dump(provenance, f, indent=2, default=str)
            else:
                f.write(provenance.model_dump_json(indent=2))

        return path


def merge_coco_shards(
    output_dir: Path, final_filename: str = "coco_labels.json", cleanup: bool = False
):
    """Merge multiple COCO JSON shards into a single canonical file."""
    shard_files = sorted(output_dir.glob("coco_shard_*.json"))
    if not shard_files:
        logger.warning(f"No COCO shards found in {output_dir}")
        return

    master_data = {"images": [], "annotations": [], "categories": []}
    global_image_id_offset = 0
    global_ann_id_offset = 0
    categories_set = False

    for shard_path in shard_files:
        with open(shard_path, "r") as f:
            shard_data = json.load(f)

        if not categories_set:
            master_data["categories"] = shard_data.get("categories", [])
            categories_set = True

        image_id_map = {}
        max_image_id = 0
        for img in shard_data.get("images", []):
            old_id = img["id"]
            new_id = old_id + global_image_id_offset
            image_id_map[old_id] = new_id
            img["id"] = new_id
            master_data["images"].append(img)
            max_image_id = max(max_image_id, old_id)

        max_ann_id = 0
        for ann in shard_data.get("annotations", []):
            old_id = ann["id"]
            new_id = old_id + global_ann_id_offset
            ann["id"] = new_id
            ann["image_id"] = image_id_map.get(ann["image_id"], ann["image_id"])
            master_data["annotations"].append(ann)
            max_ann_id = max(max_ann_id, old_id)

        global_image_id_offset += max_image_id + 1
        global_ann_id_offset += max_ann_id + 1

    final_path = output_dir / final_filename
    with open(final_path, "w") as f:
        json.dump(master_data, f, indent=2)
    logger.info(f"Merged {len(shard_files)} shards into {final_path}")

    if cleanup:
        for shard_path in shard_files:
            shard_path.unlink()
        logger.info("Cleaned up COCO shard files.")


def merge_csv_shards(
    output_dir: Path, final_filename: str = "ground_truth.csv", cleanup: bool = False
):
    """Merge multiple CSV shards into a single canonical file."""
    shard_files = sorted(output_dir.glob("tags_shard_*.csv"))
    if not shard_files:
        logger.warning(f"No CSV shards found in {output_dir}")
        return

    final_path = output_dir / final_filename
    with open(final_path, "w", newline="") as fout:
        writer = csv.writer(fout)
        header_written = False

        for shard_path in shard_files:
            with open(shard_path, "r", newline="") as fin:
                reader = csv.reader(fin)
                header = next(reader, None)
                if not header_written and header:
                    writer.writerow(header)
                    header_written = True

                for row in reader:
                    writer.writerow(row)

    logger.info(f"Merged {len(shard_files)} shards into {final_path}")

    if cleanup:
        for shard_path in shard_files:
            shard_path.unlink()
        logger.info("Cleaned up CSV shard files.")


def merge_rich_truth_shards(
    output_dir: Path, final_filename: str = "rich_truth.json", cleanup: bool = False
):
    """Merge multiple RichTruth JSON shards into a single canonical file."""
    shard_files = sorted(output_dir.glob("rich_truth_shard_*.json"))
    if not shard_files:
        logger.warning(f"No RichTruth shards found in {output_dir}")
        return

    master_data = []
    for shard_path in shard_files:
        with open(shard_path, "r") as f:
            shard_data = json.load(f)
            master_data.extend(shard_data)

    final_path = output_dir / final_filename
    with open(final_path, "w") as f:
        json.dump(master_data, f, indent=2)
    logger.info(f"Merged {len(shard_files)} shards into {final_path}")

    if cleanup:
        for shard_path in shard_files:
            shard_path.unlink()
        logger.info("Cleaned up RichTruth shard files.")
