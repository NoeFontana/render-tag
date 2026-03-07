"""
FiftyOne tool for visualizing render-tag datasets.
"""

import json
from pathlib import Path
from typing import Any

import fiftyone as fo


def create_dataset(name: str) -> fo.Dataset:
    """
    Create a new FiftyOne dataset with the required schema.
    """
    if fo.dataset_exists(name):
        fo.delete_dataset(name)

    dataset = fo.Dataset(name)

    # Register custom metadata fields on detections
    # Standard COCO importer uses 'detections' field
    dataset.add_sample_field(
        "detections.detections.distance",
        fo.FloatField,
        description="Euclidean distance to camera (meters)",
    )
    dataset.add_sample_field(
        "detections.detections.angle_of_incidence",
        fo.FloatField,
        description="Angle of incidence (degrees)",
    )
    dataset.add_sample_field(
        "detections.detections.ppm",
        fo.FloatField,
        description="Pixels Per Module (resolution)",
    )
    dataset.add_sample_field(
        "detections.detections.position",
        fo.ListField,
        description="3D position [x, y, z]",
    )
    dataset.add_sample_field(
        "detections.detections.rotation_quaternion",
        fo.ListField,
        description="3D rotation [w, x, y, z]",
    )

    return dataset


def load_dataset_from_coco(dataset_dir: Path, name: str) -> fo.Dataset:
    """
    Load a COCO dataset into FiftyOne.
    """
    if fo.dataset_exists(name):
        fo.delete_dataset(name)

    labels_path = dataset_dir / "coco_labels.json"

    return fo.Dataset.from_dir(
        dataset_dir=str(dataset_dir),
        dataset_type=fo.types.COCODetectionDataset,
        labels_path=str(labels_path) if labels_path.exists() else None,
        data_path=str(dataset_dir),
        name=name,
    )


def index_rich_truth(
    rich_truth_data: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
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
    corners: list[list[float]], width: float = 1.0, height: float = 1.0, normalized: bool = False
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
    normalized: bool = False,
) -> fo.Polyline:
    """
    Convert COCO segmentation to FiftyOne Polyline.
    """
    pts = []
    raw_pts = segmentation[0] if isinstance(segmentation[0], list) else segmentation

    for i in range(0, len(raw_pts), 2):
        px, py = raw_pts[i], raw_pts[i + 1]
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
    return bool(x < -eps or y < -eps or (x + w) > 1.0 + eps or (y + h) > 1.0 + eps)


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
    return bool(ppm > 50.0 and rel_area < 0.001)


def compute_iou(box1: list[float], box2: list[float]) -> float:
    """
    Compute IoU between two bboxes [x, y, w, h].
    """
    # Convert to [x1, y1, x2, y2]
    b1_x1, b1_y1, b1_x2, b1_y2 = box1[0], box1[1], box1[0] + box1[2], box1[1] + box1[3]
    b2_x1, b2_y1, b2_x2, b2_y2 = box2[0], box2[1], box2[0] + box2[2], box2[1] + box2[3]

    # Intersection
    inter_x1 = max(b1_x1, b2_x1)
    inter_y1 = max(b1_y1, b2_y1)
    inter_x2 = min(b1_x2, b2_x2)
    inter_y2 = min(b1_y2, b2_y2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    # Union
    area1 = box1[2] * box1[3]
    area2 = box2[2] * box2[3]
    union_area = area1 + area2 - inter_area

    if union_area == 0:
        return 0.0
    return inter_area / union_area


def check_overlap(detections: list[fo.Detection], iou_threshold: float = 0.5) -> bool:
    """
    Check if any two tags overlap significantly.
    """
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
        # COCO importer uses 'detections'
        if not hasattr(sample, "detections") or not sample.detections:
            continue

        detections = sample.detections.detections
        if any(check_oob(d) for d in detections):
            tags.append("ERR_OOB")
        if any(check_scale_drift(d) for d in detections):
            tags.append("ERR_SCALE_DRIFT")
        if check_overlap(detections):
            tags.append("ERR_OVERLAP")

        if tags:
            sample.tags.extend(tags)
            sample.save()


def visualize_fiftyone(
    dataset_path: Path, address: str = "0.0.0.0", port: int = 5151, remote: bool = False
) -> None:
    """
    Main entry point for FiftyOne visualization.
    """
    dataset_name = f"render-tag-{dataset_path.name}"

    # 1. Load Base COCO
    print(f"Loading COCO dataset from {dataset_path}...")
    dataset = load_dataset_from_coco(dataset_path, dataset_name)

    # 2. Load and Index Rich Truth
    rich_truth_file = dataset_path / "rich_truth.json"
    if rich_truth_file.exists():
        print(f"Hydrating with rich truth from {rich_truth_file}...")
        with open(rich_truth_file) as f:
            rich_truth_data = json.load(f)

        rich_index = index_rich_truth(rich_truth_data)

        # Hydrate Dataset
        for sample in dataset:
            width = sample.metadata.width if sample.metadata else 1.0
            height = sample.metadata.height if sample.metadata else 1.0

            if not hasattr(sample, "detections") or not sample.detections:
                continue

            detections = sample.detections.detections
            new_keypoints = []
            new_polylines = []

            for det in detections:
                img_stem = Path(sample.filepath).stem
                # FiftyOne maps COCO attributes to 'attributes' dict or direct fields
                # In latest FiftyOne, 'tag_id' from COCO is often a direct field
                # if it was in 'attributes'
                tag_id = det.get_field("tag_id") if hasattr(det, "get_field") else det.get("tag_id")

                # If not found, check attributes
                if tag_id is None and "tag_id" in det.attributes:
                    tag_id = det.attributes["tag_id"]

                # Try to find record
                record = rich_index.get((img_stem, tag_id))
                if record:
                    hydrate_detection(det, record)

                    # Add layers
                    if "corners" in record:
                        kps = map_corners_to_keypoints(record["corners"], width, height)
                        new_keypoints.extend(kps.keypoints)

                        poly = get_polyline_from_segmentation(record["corners"], width, height)
                        new_polylines.extend([poly])

            if new_keypoints:
                sample["corners"] = fo.Keypoints(keypoints=new_keypoints)
            if new_polylines:
                sample["polygons"] = fo.Polylines(polylines=new_polylines)

            sample.save()

    # 3. Run Auditor
    print("Running automated auditor...")
    audit_dataset(dataset)

    # 5. Launch App
    print(f"Launching FiftyOne App on {address}:{port}...")
    session = fo.launch_app(dataset, address=address, port=port, remote=remote)

    # Block so the server stays alive until the user closes it (or Ctrl+C)
    session.wait()
