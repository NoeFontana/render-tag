"""
FiftyOne tool for visualizing render-tag datasets.
"""

import json
from pathlib import Path
from typing import Any

import fiftyone as fo
import numpy as np
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from render_tag.generation.projection_math import (
    quaternion_xyzw_to_matrix,
)

try:
    from fiftyone.core.session import Session
except ImportError:
    Session = None


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
        description="3D rotation [x, y, z, w]",
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
) -> dict[tuple[str, int, str], dict[str, Any]]:
    """
    Index rich truth data by (image_id, tag_id, record_type) for rapid lookup.
    """
    index = {}
    for record in rich_truth_data:
        image_id = record.get("image_id")
        tag_id = record.get("tag_id")
        record_type = record.get("record_type", "TAG")
        if image_id is not None and tag_id is not None:
            index[(str(image_id), int(tag_id), str(record_type))] = record
    return index


def hydrate_detection(detection: fo.Detection, record: dict[str, Any]) -> None:
    """
    Populate a FiftyOne Detection object with custom metadata.
    """
    fields = [
        "distance",
        "angle_of_incidence",
        "ppm",
        "position",
        "rotation_quaternion",
        "k_matrix",
        "resolution",
        "velocity",
        "shutter_time_ms",
        "rolling_shutter_ms",
        "fstop",
        "record_type",
    ]
    for field in fields:
        if field in record:
            detection[field] = record[field]


def map_corners_to_keypoints(
    corners: list[list[float]],
    width: float = 1.0,
    height: float = 1.0,
    normalized: bool = False,
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


def get_polyline_points(
    segmentation: list[Any],
    width: float = 1.0,
    height: float = 1.0,
    normalized: bool = False,
) -> list[list[float]]:
    """
    Extract normalized points for FiftyOne Polylines/Detections.
    """
    pts = []

    # Handle case: [[x1, y1], [x2, y2], ...] (Rich Truth style)
    if (
        len(segmentation) > 0
        and isinstance(segmentation[0], (list, tuple))
        and len(segmentation[0]) == 2
    ):
        for pt in segmentation:
            px, py = pt[0], pt[1]
            if not normalized:
                px /= width
                py /= height
            pts.append([px, py])
    else:
        # Handle case: [x1, y1, x2, y2, ...] (Standard COCO)
        raw_pts = segmentation[0] if isinstance(segmentation[0], list) else segmentation
        for i in range(0, len(raw_pts), 2):
            px, py = raw_pts[i], raw_pts[i + 1]
            if not normalized:
                px /= width
                py /= height
            pts.append([px, py])

    return pts


def project_tag_axes(
    record: dict[str, Any],
    k_matrix: list[list[float]],
    resolution: list[int],
) -> dict[str, fo.Polyline] | None:
    """
    Project 3D axes at the tag center using its pose metadata (Single Source of Truth).
    """
    pos = record.get("position")  # [x, y, z] in camera space
    quat = record.get("rotation_quaternion")  # [x, y, z, w] in camera space

    # Use tag size to determine axis length (e.g., half the tag size). Fallback to 5cm.
    tag_size_mm = record.get("tag_size_mm", 100.0)
    axis_len_m = (tag_size_mm / 1000.0) / 2.0
    if axis_len_m <= 0:
        axis_len_m = 0.05

    if pos is None or quat is None:
        return None

    width, height = resolution
    k_np = np.array(k_matrix)
    r_mat = quaternion_xyzw_to_matrix(quat)
    t_vec = np.array(pos)

    # Local axes points (Origin at center)
    local_origin = np.array([0.0, 0.0, 0.0])
    local_x = np.array([axis_len_m, 0.0, 0.0])  # +X right
    local_y = np.array([0.0, axis_len_m, 0.0])  # +Y down

    # Local +Z points INTO the tag face (away from camera if facing)
    local_z = np.array([0.0, 0.0, axis_len_m])

    # Transform to camera space
    def to_cam(p_local):
        return t_vec + r_mat @ p_local

    # Project to 2D pixels and normalize to [0, 1] for FiftyOne
    def project(p_cam):
        if p_cam[2] <= 1e-6:
            return None  # Behind camera
        p_2d_hom = k_np @ p_cam
        px = p_2d_hom[0] / p_2d_hom[2]
        py = p_2d_hom[1] / p_2d_hom[2]
        return [float(px / width), float(py / height)]

    origin_2d = project(to_cam(local_origin))
    x_2d = project(to_cam(local_x))
    y_2d = project(to_cam(local_y))
    z_2d = project(to_cam(local_z))

    # If any point is behind the camera, skip rendering the axes
    if not all([origin_2d, x_2d, y_2d, z_2d]):
        return None

    return {
        "axis_x": fo.Polyline(label="X", points=[[origin_2d, x_2d]]),
        "axis_y": fo.Polyline(label="Y", points=[[origin_2d, y_2d]]),
        "axis_z": fo.Polyline(label="Z", points=[[origin_2d, z_2d]]),
    }


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
    b1_x1, b1_y1, b1_x2, b1_y2 = box1[0], box1[1], box1[0] + box1[2], box1[1] + box1[3]
    b2_x1, b2_y1, b2_x2, b2_y2 = box2[0], box2[1], box2[0] + box2[2], box2[1] + box2[3]

    inter_x1 = max(b1_x1, b2_x1)
    inter_y1 = max(b1_y1, b2_y1)
    inter_x2 = min(b1_x2, b2_x2)
    inter_y2 = min(b1_y2, b2_y2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

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


def create_error_view(dataset: fo.Dataset) -> None:
    """
    Create a saved view for samples with errors.
    """
    error_tags = ["ERR_OOB", "ERR_OVERLAP", "ERR_SCALE_DRIFT"]
    view = dataset.match_tags(error_tags)
    dataset.save_view("Anomalies", view)


def find_active_session() -> fo.Session | None:
    """
    Find an active FiftyOne session if one exists.
    """
    if Session and hasattr(Session, "_instances") and Session._instances:
        return next(iter(Session._instances.values()))
    return None


def visualize_fiftyone(
    dataset_path: Path, address: str = "0.0.0.0", port: int = 5151, remote: bool = False
) -> None:
    """
    Main entry point for FiftyOne visualization.
    """
    dataset_name = f"render-tag-{dataset_path.name}"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        expand=True,
    ) as progress:
        task_load = progress.add_task("Loading COCO dataset", total=1)
        dataset = load_dataset_from_coco(dataset_path, dataset_name)
        progress.update(task_load, advance=1)

        task_meta = progress.add_task("Computing image metadata", total=1)
        dataset.compute_metadata()
        progress.update(task_meta, advance=1)

        rich_truth_file = dataset_path / "rich_truth.json"
        if rich_truth_file.exists():
            with open(rich_truth_file) as f:
                rich_truth_data = json.load(f)

            rich_index = index_rich_truth(rich_truth_data)

            task_hydrate = progress.add_task("Hydrating with rich truth", total=len(dataset))
            for sample in dataset:
                width = sample.metadata.width if sample.metadata else 1.0
                height = sample.metadata.height if sample.metadata else 1.0

                if not hasattr(sample, "detections") or not sample.detections:
                    progress.update(task_hydrate, advance=1)
                    continue

                detections = sample.detections.detections
                new_keypoints = []
                new_axis_x = []
                new_axis_y = []
                new_axis_z = []

                for det in detections:
                    img_stem = Path(sample.filepath).stem
                    tag_id = (
                        det.get_field("tag_id") if hasattr(det, "get_field") else det.get("tag_id")
                    )

                    if tag_id is None and "tag_id" in det.attributes:
                        tag_id = det.attributes["tag_id"]

                    record_type = (
                        det.get_field("record_type")
                        if hasattr(det, "get_field")
                        else det.get("record_type")
                    )
                    if record_type is None and "record_type" in det.attributes:
                        record_type = det.attributes["record_type"]

                    record = rich_index.get((img_stem, tag_id, record_type))
                    if record:
                        hydrate_detection(det, record)

                        if "corners" in record:
                            pts = get_polyline_points(record["corners"], width, height)
                            det.segmentation = [pts]

                            kps = map_corners_to_keypoints(record["corners"], width, height)
                            new_keypoints.extend(kps.keypoints)

                            # 3D Axes Overlay
                            if "k_matrix" in record and "resolution" in record:
                                axes = project_tag_axes(
                                    record,
                                    k_matrix=record["k_matrix"],
                                    resolution=record["resolution"],
                                )
                                if axes:
                                    new_axis_x.append(axes["axis_x"])
                                    new_axis_y.append(axes["axis_y"])
                                    new_axis_z.append(axes["axis_z"])

                if new_keypoints:
                    sample["corners"] = fo.Keypoints(keypoints=new_keypoints)
                if new_axis_x:
                    sample["axis_x"] = fo.Polylines(polylines=new_axis_x)
                    sample["axis_y"] = fo.Polylines(polylines=new_axis_y)
                    sample["axis_z"] = fo.Polylines(polylines=new_axis_z)

                sample.save()
                progress.update(task_hydrate, advance=1)

        task_audit = progress.add_task("Running automated auditor", total=1)
        audit_dataset(dataset)
        progress.update(task_audit, advance=1)

        task_views = progress.add_task("Configuring saved views", total=1)
        create_error_view(dataset)
        progress.update(task_views, advance=1)

    # Apply color scheme for axes visualization targeting separate fields
    color_scheme = fo.ColorScheme(
        multicolor_keypoints=True,
        color_pool=["#FF0000", "#00FF00", "#0000FF", "#000000"],
        fields=[
            {"path": "axis_x", "colorByAttribute": "path", "fieldColor": "#FF0000"},
            {"path": "axis_y", "colorByAttribute": "path", "fieldColor": "#00FF00"},
            {"path": "axis_z", "colorByAttribute": "path", "fieldColor": "#0000FF"},
            {
                "path": "detections",
                "colorByAttribute": "record_type",
                "valueColors": [
                    {"value": "TAG", "color": "#00FF00"},
                    {"value": "BOARD", "color": "#FF00FF"},
                    {"value": "CHARUCO_SADDLE", "color": "#00FFFF"},
                ],
            },
            {
                "path": "corners",
                "colorByAttribute": "label",
                "valueColors": [
                    {"value": "0", "color": "#FF00FF"},
                    {"value": "1", "color": "#00FFFF"},
                    {"value": "2", "color": "#FFFF00"},
                    {"value": "3", "color": "#FFFFFF"},
                ],
            },
        ],
    )
    dataset.app_config.color_scheme = color_scheme
    dataset.save()

    session = find_active_session()
    if session:
        print(f"Reusing active FiftyOne session on {session.url}...")
        session.dataset = dataset
    else:
        print(f"Launching FiftyOne App on {address}:{port}...")
        session = fo.launch_app(dataset, address=address, port=port, remote=remote)

    session.wait()
