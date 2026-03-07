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


def create_id_label(center: list[float], tag_id: int) -> fo.Keypoint:
    """
    Create a labeled keypoint for the tag ID.
    """
    return fo.Keypoint(label=f"ID: {tag_id}", points=[center])


def quaternion_to_matrix(q: list[float]) -> np.ndarray:
    """
    Convert a wxyz quaternion to a 3x3 rotation matrix.
    """
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * y**2 - 2 * z**2, 2 * x * y - 2 * w * z, 2 * x * z + 2 * w * y],
            [2 * x * y + 2 * w * z, 1 - 2 * x**2 - 2 * z**2, 2 * y * z - 2 * w * x],
            [2 * x * z - 2 * w * y, 2 * y * z + 2 * w * x, 1 - 2 * x**2 - 2 * y**2],
        ]
    )


def project_tag_axes(
    record: dict[str, Any],
    k_matrix: list[list[float]],
    resolution: list[int],
    axis_length: float = 0.05,
) -> dict[str, fo.Polyline] | None:
    """
    Project 3D axes at the tag Top-Left corner.
    Uses true 2D corners for X/Y, and projects Z outwards.
    """
    pos = record.get("position")  # [x, y, z] in camera space
    quat = record.get("rotation_quaternion")  # [w, x, y, z] in camera space
    corners_2d = record.get("corners")

    if pos is None or quat is None or not corners_2d or len(corners_2d) < 4:
        return None

    width, height = resolution

    # Extract the true 2D corners in normalized space
    normalized_corners = get_polyline_points(corners_2d, width, height, normalized=False)
    tl = normalized_corners[0]
    tr = normalized_corners[1]
    bl = normalized_corners[3]

    # Calculate Z axis in 3D
    # Use standard 0.1 size for offset, m=0.05
    m = 0.05
    pts_3d = np.array(
        [
            [-m, m, 0],  # Origin (estimated Top-Left in 3D)
            [-m, m, -0.1],  # Z-axis end (Outward towards the camera is local -Z)
        ]
    )

    r_mat = quaternion_to_matrix(quat)
    t_vec = np.array(pos)

    pts_cam = (r_mat @ pts_3d.T).T + t_vec
    k_np = np.array(k_matrix)
    pts_2d_hom = (k_np @ pts_cam.T).T
    pts_2d = pts_2d_hom[:, :2] / pts_2d_hom[:, 2:3]

    pts_2d[:, 0] /= width
    pts_2d[:, 1] /= height

    z_origin = pts_2d[0]
    z_end = pts_2d[1]
    z_vector = z_end - z_origin

    true_z_end = [tl[0] + float(z_vector[0]), tl[1] + float(z_vector[1])]

    return {
        "axis_x": fo.Polyline(label="X", points=[[tl, tr]]),
        "axis_y": fo.Polyline(label="Y", points=[[tl, bl]]),
        "axis_z": fo.Polyline(label="Z", points=[[tl, true_z_end]]),
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
    try:
        from fiftyone.core.session import Session

        if hasattr(Session, "_instances") and Session._instances:
            return next(iter(Session._instances.values()))
    except (ImportError, AttributeError):
        pass
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

                # Try to load camera metadata for projection
                img_path = Path(sample.filepath)
                meta_path = img_path.parent / f"{img_path.stem}_meta.json"
                cam_meta = None
                if meta_path.exists():
                    with open(meta_path) as f:
                        cam_meta = json.load(f)

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

                    record = rich_index.get((img_stem, tag_id))
                    if record:
                        hydrate_detection(det, record)

                        if "corners" in record:
                            pts = get_polyline_points(record["corners"], width, height)
                            det.segmentation = [pts]

                            kps = map_corners_to_keypoints(record["corners"], width, height)
                            new_keypoints.extend(kps.keypoints)

                            # ID Label Overlay
                            center_px = np.mean(record["corners"], axis=0)
                            center_norm = [center_px[0] / width, center_px[1] / height]
                            id_kp = create_id_label(center_norm, tag_id)
                            new_keypoints.append(id_kp)

                            # 3D Axes Overlay
                            if cam_meta:
                                try:
                                    cam = cam_meta["recipe_snapshot"]["cameras"][0]
                                    axes = project_tag_axes(
                                        record,
                                        k_matrix=cam["intrinsics"]["k_matrix"],
                                        resolution=cam["intrinsics"]["resolution"],
                                    )
                                    if axes:
                                        new_axis_x.append(axes["axis_x"])
                                        new_axis_y.append(axes["axis_y"])
                                        new_axis_z.append(axes["axis_z"])
                                except (KeyError, IndexError):
                                    pass

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
        color_pool=["#FF0000", "#00FF00", "#0000FF", "#000000"],
        fields=[
            {"path": "axis_x", "colorByAttribute": "path", "fieldColor": "#FF0000"},
            {"path": "axis_y", "colorByAttribute": "path", "fieldColor": "#00FF00"},
            {"path": "axis_z", "colorByAttribute": "path", "fieldColor": "#0000FF"},
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
