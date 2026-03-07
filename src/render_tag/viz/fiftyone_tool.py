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

def hydrate_detection(detection: fo.Detection, record: dict[str, Any]) -> None:
    """
    Populate a FiftyOne Detection object with custom metadata.
    """
    fields = ["distance", "angle_of_incidence", "ppm", "position", "rotation_quaternion"]
    for field in fields:
        if field in record:
            detection[field] = record[field]

def map_corners_to_keypoints(
    corners: list[list[float]], 
    width: float = 1.0, 
    height: float = 1.0,
    normalized: bool = False
) -> fo.Keypoints:
    """
    Map ordered corners to FiftyOne Keypoints with indexed labels.
    """
    kps = []
    for i, pt in enumerate(corners):
        px, py = pt[0], pt[1]
        if not normalized:
            px /= width
            py /= height
        kps.append(fo.Keypoint(label=str(i), points=[[px, py]]))
    
    return fo.Keypoints(keypoints=kps)

def get_polyline_from_segmentation(
    segmentation: list[list[float]],
    width: float = 1.0,
    height: float = 1.0,
    normalized: bool = False
) -> fo.Polyline:
    """
    Convert COCO segmentation to FiftyOne Polyline.
    """
    # COCO segmentation is [x1, y1, x2, y2, ...]
    pts = []
    raw_pts = segmentation[0] if isinstance(segmentation[0], list) else segmentation
    
    for i in range(0, len(raw_pts), 2):
        px, py = raw_pts[i], raw_pts[i+1]
        if not normalized:
            px /= width
            py /= height
        pts.append([px, py])
        
    return fo.Polyline(points=[pts], closed=True, filled=True)

def check_oob(detection: fo.Detection) -> bool:
    """
    Check if a bounding box is out of image bounds.
    """
    bbox = detection.bounding_box
    if not bbox:
        return False
    
    x, y, w, h = bbox
    eps = 1e-6
    if x < -eps or y < -eps or (x + w) > 1.0 + eps or (y + h) > 1.0 + eps:
        return True
    return False

def check_scale_drift(detection: fo.Detection, threshold: float = 0.5) -> bool:
    """
    Check for scale drift by comparing PPM metadata with Bbox area.
    """
    try:
        ppm = detection["ppm"]
    except (KeyError, AttributeError):
        ppm = None
        
    bbox = detection.bounding_box
    if ppm is None or not bbox:
        return False
    
    rel_area = bbox[2] * bbox[3]
    if ppm > 50.0 and rel_area < 0.001:
        return True
    return False

def check_overlap(detections: list[fo.Detection], iou_threshold: float = 0.5) -> bool:
    """
    Check if any two tags overlap significantly.
    """
    from fiftyone.utils.bbox import compute_iou
    for i, det1 in enumerate(detections):
        for j, det2 in enumerate(detections):
            if i >= j:
                continue
            iou = compute_iou(det1.bounding_box, det2.bounding_box)
            if iou > iou_threshold:
                return True
    return False

def audit_dataset(dataset: fo.Dataset) -> None:
    """
    Run the watchdog auditor on the dataset and tag anomalies.
    """
    for sample in dataset:
        tags = []
        if not sample.ground_truth:
            continue
            
        detections = sample.ground_truth.detections
        if any(check_oob(d) for d in detections):
            tags.append("ERR_OOB")
        if any(check_scale_drift(d) for d in detections):
            tags.append("ERR_SCALE_DRIFT")
        if check_overlap(detections):
            tags.append("ERR_OVERLAP")
            
        if tags:
            sample.tags.extend(tags)
            sample.save()
