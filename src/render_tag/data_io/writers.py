"""
Data export writers for render-tag.

This module handles writing detection annotations in various formats:
- CSV format for corner coordinates
- COCO format for instance segmentation
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from render_tag.core.logging import get_logger
from render_tag.core.schema import (
    BoardConfig,
    DetectionRecord,
    SceneProvenance,
)
from render_tag.core.schema.base import KEYPOINT_SENTINEL

# Import pure-Python geometry modules
try:
    from render_tag.data_io.annotations import (
        compute_bbox,
        compute_eval_visibility,
        format_coco_keypoints,
    )
    from render_tag.generation.math import compute_polygon_area

    GEOMETRY_AVAILABLE = True
except ImportError:
    GEOMETRY_AVAILABLE = False

logger = get_logger(__name__)

# Fields already encoded natively by the COCO annotation envelope.
# Excluded from the DetectionRecord dump to avoid duplication.
_COCO_NATIVE_FIELDS = frozenset({"image_id", "corners", "keypoints", "metadata"})


class AtomicWriter:
    """Mixin for atomic file writing using temp file + rename."""

    def _write_atomic(self, path: Path, data: Any) -> None:
        """Write data to a temp file then rename atomically."""
        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                if isinstance(data, (dict, list)):
                    json.dump(data, f, indent=2)
                else:
                    f.write(data)
                f.flush()
                os.fsync(f.fileno())

            temp_path.rename(path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise


class CSVWriter:
    """Writes detection data to a CSV file.

    Keeps the file handle open for the writer's lifetime to avoid per-row
    open/close overhead. Call close() or use as a context manager to flush.
    """

    def __init__(self, output_path: Path) -> None:
        """Initialize the CSV writer."""
        self.output_path = output_path
        self._initialized = False
        self._file = None
        self._writer = None

    def _ensure_initialized(self, num_corners: int = 4, num_keypoints: int = 0) -> None:
        """Create the file and write header if not already done."""
        if not self._initialized:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

            header = DetectionRecord.csv_header(num_corners, num_keypoints)
            self._file = open(self.output_path, "w", newline="")  # noqa: SIM115
            self._writer = csv.writer(self._file)
            self._writer.writerow(header)
            self._file.flush()
            self._initialized = True

    def write_detection(
        self,
        detection: DetectionRecord,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        """Write a single detection to the CSV file (optionally clipped)."""
        # Calibration records might not have 4 corners
        if detection.record_type == "TAG" and not detection.is_valid():
            return

        self._ensure_initialized(
            num_corners=len(detection.corners),
            num_keypoints=len(detection.keypoints) if detection.keypoints else 0,
        )

        # Delegate CSV formatting to the data record
        row = detection.to_csv_row(width=width, height=height)
        self._writer.writerow(row)

    def write_detections(self, detections: list[DetectionRecord]) -> None:
        """Write multiple detections to the CSV file."""
        for detection in detections:
            self.write_detection(detection)

    def close(self) -> None:
        """Flush and close the underlying file handle."""
        if self._file and not self._file.closed:
            self._file.flush()
            os.fsync(self._file.fileno())
            self._file.close()

    def __del__(self) -> None:
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class COCOWriter(AtomicWriter):
    """Writer for COCO format annotations."""

    def __init__(
        self,
        output_dir: Path,
        filename: str = "annotations.json",
        eval_margin_px: int = 0,
    ) -> None:
        """Initialize the COCO writer."""
        self.output_dir = output_dir
        self.filename = filename
        self._eval_margin_px = eval_margin_px
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
                    "tl",
                    "tr",
                    "br",
                    "bl",
                ],  # Industry standard (CW from TL)
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

        if corners is None or len(corners) == 0:
            raise ValueError("Annotation must have at least one point")

        annotation_id = self._next_annotation_id
        self._next_annotation_id += 1

        # Clip corners if dimensions provided
        if width is not None or height is not None:
            corners = [
                (
                    max(0.0, min(float(width or 1e9), c[0])) if c[0] > -999999.0 else c[0],
                    max(0.0, min(float(height or 1e9), c[1])) if c[1] > -999999.0 else c[1],
                )
                for c in corners
            ]

        # Handle point annotations (e.g. saddle points)
        if len(corners) < 3:
            # For 1 or 2 points, bbox is small area around points
            x_coords = [c[0] for c in corners]
            y_coords = [c[1] for c in corners]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)

            # If it's a single point, give it a tiny 1px box for COCO compatibility
            if min_x == max_x:
                min_x -= 0.5
                max_x += 0.5
            if min_y == max_y:
                min_y -= 0.5
                max_y += 0.5

            bbox = [min_x, min_y, max_x - min_x, max_y - min_y]
            area = (max_x - min_x) * (max_y - min_y)
            segmentation = []  # COCO polygons require >= 3 points
        else:
            # Standard Polygon Path
            # 1. Use pure-Python utility for bbox
            dist_coeffs = getattr(detection, "distortion_coeffs", None) or None
            dist_model = getattr(detection, "distortion_model", "none") or "none"
            bbox = compute_bbox(
                np.array(corners),
                detection=detection,
                distortion_coeffs=dist_coeffs,
                distortion_model=dist_model,
            )

            # 2. Use pure-Python utility for area
            area = compute_polygon_area(np.array(corners))

            # 3. Serialize corners directly: the 3D asset contract guarantees CW from TL.
            # Segmentation:
            segmentation = []
            for corner in corners:
                segmentation.extend([corner[0], corner[1]])

        # Keypoints:
        if len(corners) == 4 and width is not None and height is not None:
            corners_array = np.array(corners)
            vis = compute_eval_visibility(
                corners_array, int(width), int(height), self._eval_margin_px
            )
            keypoints = format_coco_keypoints(corners_array, visibility=vis)
            num_keypoints = int(np.sum(vis))
        elif len(corners) == 4:
            keypoints = format_coco_keypoints(np.array(corners))
            num_keypoints = 4
        else:
            # Use raw points as keypoints
            keypoints = format_coco_keypoints(np.array(corners))
            num_keypoints = len(corners)

        if detection and detection.keypoints:
            kp_array = np.array(detection.keypoints)
            sentinel_mask = np.all(kp_array == KEYPOINT_SENTINEL, axis=1)
            vis = ~sentinel_mask
            extra_kp = format_coco_keypoints(kp_array, visibility=vis)
            keypoints.extend(extra_kp)
            num_keypoints += int(np.sum(vis))  # Only count visible

        # Prepare attributes: dynamic dump excludes COCO-native fields
        if detection:
            attributes = detection.model_dump(mode="json", exclude=_COCO_NATIVE_FIELDS)
            # Fallback: pixel_area may be 0.0 if not computed; use polygon area instead
            if attributes.get("pixel_area") is None:
                attributes["pixel_area"] = area
            # Merge unstructured metadata without overwriting schema fields
            for k, v in detection.metadata.items():
                if k not in attributes:
                    attributes[k] = v
        else:
            attributes = {}

        self.annotations.append(
            {
                "id": annotation_id,
                "image_id": image_id,
                "category_id": category_id,
                "segmentation": [segmentation] if segmentation else [],
                "bbox": bbox,
                "area": area,
                "keypoints": keypoints,
                "num_keypoints": num_keypoints,
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
            "Saving COCO annotations",
            path=str(output_path),
            images=len(self.images),
            annotations=len(self.annotations),
        )

        if not self._dirty:
            logger.debug("COCOWriter: No new annotations, skipping save")
            return output_path

        coco_data = {
            "images": self.images,
            "annotations": self.annotations,
            "categories": self.categories,
        }

        self._write_atomic(output_path, coco_data)

        self._dirty = False
        return output_path


class RichTruthWriter(AtomicWriter):
    """Writer for structured JSON 'Data Product' containing all metadata."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self._detections: list[dict] = []

    def add_detection(self, detection: DetectionRecord) -> None:
        """Add a detection record to the output list."""
        record = detection.model_dump(mode="json")
        self._detections.append(record)

    def save(self) -> Path:
        """Save all detections to the JSON file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_atomic(self.output_path, self._detections)
        return self.output_path


class ProvenanceWriter(AtomicWriter):
    """Writer for a unified dataset provenance mapping (image_id -> SceneRecipe)."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self._provenance: dict[str, Any] = {}

    def add_provenance(self, image_id: str, provenance: dict[str, Any] | SceneProvenance) -> None:
        """Add provenance for a single image."""
        model_dump = getattr(provenance, "model_dump", None)
        data = model_dump(mode="json") if callable(model_dump) else provenance
        self._provenance[image_id] = data

    def save(self) -> Path:
        """Save the unified provenance mapping to a JSON file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_atomic(self.output_path, self._provenance)
        return self.output_path


class BoardConfigWriter:
    """Writer for calibration board configuration."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize the BoardConfig writer.

        Args:
            output_dir: Root directory for dataset output.
        """
        self.output_dir = output_dir

    def write_config(self, board_config: BoardConfig, filename: str = "board_config.json") -> Path:
        """Save the board configuration to a JSON file.

        Args:
            board_config: The BoardConfig instance to save.
            filename: Name of the output JSON file.

        Returns:
            Path to the written file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / filename

        with open(output_path, "w") as f:
            f.write(board_config.model_dump_json(indent=2))

        return output_path


def _write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON data atomically using temp file + rename."""
    temp_path = path.with_suffix(".tmp")
    try:
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_path.rename(path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


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
        with open(shard_path) as f:
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
    _write_json_atomic(final_path, master_data)
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
    temp_path = final_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", newline="") as fout:
            writer = csv.writer(fout)
            header_written = False

            for shard_path in shard_files:
                with open(shard_path, newline="") as fin:
                    reader = csv.reader(fin)
                    header = next(reader, None)
                    if not header_written and header:
                        writer.writerow(header)
                        header_written = True

                    for row in reader:
                        writer.writerow(row)

            fout.flush()
            os.fsync(fout.fileno())

        temp_path.rename(final_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

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
        with open(shard_path) as f:
            shard_data = json.load(f)
            master_data.extend(shard_data)

    final_path = output_dir / final_filename
    _write_json_atomic(final_path, master_data)
    logger.info(f"Merged {len(shard_files)} shards into {final_path}")

    if cleanup:
        for shard_path in shard_files:
            shard_path.unlink()
        logger.info("Cleaned up RichTruth shard files.")


def merge_provenance_shards(
    output_dir: Path, final_filename: str = "provenance.json", cleanup: bool = False
):
    """Merge multiple provenance JSON shards into a single canonical file."""
    shard_files = sorted(output_dir.glob("provenance_shard_*.json"))
    if not shard_files:
        return

    master_data = {}
    for shard_path in shard_files:
        with open(shard_path) as f:
            shard_data = json.load(f)
            master_data.update(shard_data)

    final_path = output_dir / final_filename
    _write_json_atomic(final_path, master_data)
    logger.info(f"Merged {len(shard_files)} shards into {final_path}")

    if cleanup:
        for shard_path in shard_files:
            shard_path.unlink()
        logger.info("Cleaned up provenance shard files.")
