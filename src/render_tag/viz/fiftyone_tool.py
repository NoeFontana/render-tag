"""
FiftyOne tool for visualizing render-tag datasets.
"""

from pathlib import Path
from typing import Any

import fiftyone as fo

def create_dataset(name: str) -> fo.Dataset:
    """
    Create a new FiftyOne dataset with the required schema.
    """
    dataset = fo.Dataset(name)
    
    # Register custom metadata fields on detections
    dataset.add_sample_field(
        "ground_truth.detections.distance",
        fo.FloatField,
        description="Euclidean distance to camera (meters)",
    )
    dataset.add_sample_field(
        "ground_truth.detections.angle_of_incidence",
        fo.FloatField,
        description="Angle of incidence (degrees)",
    )
    dataset.add_sample_field(
        "ground_truth.detections.ppm",
        fo.FloatField,
        description="Pixels Per Module (resolution)",
    )
    dataset.add_sample_field(
        "ground_truth.detections.position",
        fo.ListField,
        description="3D position [x, y, z]",
    )
    dataset.add_sample_field(
        "ground_truth.detections.rotation_quaternion",
        fo.ListField,
        description="3D rotation [w, x, y, z]",
    )
    
    return dataset

def load_dataset_from_coco(dataset_dir: Path, name: str) -> fo.Dataset:
    """
    Load a COCO dataset into FiftyOne.
    """
    return fo.Dataset.from_dir(
        dataset_dir=str(dataset_dir),
        dataset_type=fo.types.COCODetectionDataset,
        name=name,
    )

def index_rich_truth(rich_truth_data: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    """
    Index rich truth data by (image_id, tag_id) for rapid lookup.
    """
    index = {}
    for record in rich_truth_data:
        image_id = record.get("image_id")
        tag_id = record.get("tag_id")
        if image_id is not None and tag_id is not None:
            index[(str(image_id), int(tag_id))] = record
    return index
