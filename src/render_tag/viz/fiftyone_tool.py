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
    apply_distortion_by_model,
    quaternion_wxyz_to_matrix,
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

    # Hydrate board_definition for BOARD records
    board_def = record.get("board_definition")
    if board_def and isinstance(board_def, dict):
        detection["board_type"] = board_def.get("type")
        detection["board_rows"] = board_def.get("rows")
        detection["board_cols"] = board_def.get("cols")
        detection["square_size_mm"] = board_def.get("square_size_mm")
        detection["marker_size_mm"] = board_def.get("marker_size_mm")
        detection["board_dictionary"] = board_def.get("dictionary")
        detection["total_keypoints"] = board_def.get("total_keypoints")


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


def _is_sentinel(pt: list[float] | tuple[float, float]) -> bool:
    """Check if a keypoint is the out-of-frame sentinel (-1, -1)."""
    return pt[0] == -1.0 and pt[1] == -1.0


def map_calibration_keypoints(
    keypoints: list[list[float] | tuple[float, float]],
    width: float,
    height: float,
) -> list[fo.Keypoint]:
    """Map calibration keypoints to FiftyOne Keypoints, filtering sentinels.

    Visible keypoints are labeled with their index. Sentinels are excluded
    so that FiftyOne renders only the in-frame saddle points.
    """
    kps = []
    for i, pt in enumerate(keypoints):
        if _is_sentinel(pt):
            continue
        px = pt[0] / width
        py = pt[1] / height
        kps.append(fo.Keypoint(label=str(i), points=[[px, py]]))
    return kps


def build_calibration_skeleton(rows: int, cols: int) -> fo.KeypointSkeleton:
    """Build a grid skeleton for calibration saddle points.

    For a ChArUco board with R rows and C cols, there are (R-1)*(C-1)
    saddle points arranged in a grid. The skeleton connects horizontally
    adjacent and vertically adjacent points.
    """
    inner_rows = rows - 1
    inner_cols = cols - 1
    labels = [str(i) for i in range(inner_rows * inner_cols)]
    edges = []
    for r in range(inner_rows):
        for c in range(inner_cols):
            idx = r * inner_cols + c
            if c + 1 < inner_cols:
                edges.append([idx, idx + 1])
            if r + 1 < inner_rows:
                edges.append([idx, idx + inner_cols])
    return fo.KeypointSkeleton(labels=labels, edges=edges)


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
    distortion_coeffs: list[float] | None = None,
    distortion_model: str = "none",
) -> dict[str, fo.Polyline] | None:
    """
    Project 3D axes at the tag origin (geometric center) using its pose metadata.
    """
    pos = record.get("position")  # [x, y, z] in camera space
    quat = record.get("rotation_quaternion")  # [w, x, y, z] in camera space

    # Use tag size to determine axis length (e.g., half the tag size). Fallback to 5cm.
    tag_size_mm = record.get("tag_size_mm", 100.0)
    axis_len_m = (tag_size_mm / 1000.0) / 2.0
    if axis_len_m <= 0:
        axis_len_m = 0.05

    if pos is None or quat is None:
        return None

    width, height = resolution
    k_np = np.array(k_matrix)
    fx, fy = k_np[0, 0], k_np[1, 1]
    cx, cy = k_np[0, 2], k_np[1, 2]
    r_mat = quaternion_wxyz_to_matrix(quat)
    t_vec = np.array(pos)
    coeffs = distortion_coeffs or []

    # Local axes points (Origin at geometric center of the black border)
    local_origin = np.array([0.0, 0.0, 0.0])
    local_x = np.array([axis_len_m, 0.0, 0.0])  # +X right
    local_y = np.array([0.0, axis_len_m, 0.0])  # +Y down

    # Local +Z points INTO the tag face
    local_z = np.array([0.0, 0.0, axis_len_m])

    # Transform to camera space
    def to_cam(p_local):
        return t_vec + r_mat @ p_local

    # Project to 2D pixels and normalize to [0, 1] for FiftyOne.
    # Apply the distortion model before the K multiply so axis endpoints land
    # on the correct distorted-image coordinates.
    def project(p_cam):
        if p_cam[2] <= 1e-6:
            return None  # Behind camera
        x_n = p_cam[0] / p_cam[2]
        y_n = p_cam[1] / p_cam[2]
        xd, yd = apply_distortion_by_model(
            np.array([x_n]), np.array([y_n]), coeffs, distortion_model
        )
        px = fx * xd[0] + cx
        py = fy * yd[0] + cy
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


def create_saved_views(dataset: fo.Dataset) -> None:
    """Create saved views for anomalies and calibration boards."""
    error_tags = ["ERR_OOB", "ERR_OVERLAP", "ERR_SCALE_DRIFT"]
    error_view = dataset.match_tags(error_tags)
    dataset.save_view("Anomalies", error_view)

    # Calibration view: samples that have calibration_points
    cal_view = dataset.exists("calibration_points")
    if len(cal_view) > 0:
        dataset.save_view("Calibration Boards", cal_view)


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
    calibration_skeleton_dims: tuple[int, int] | None = None

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
                new_calibration_kps = []
                new_axis_x = []
                new_axis_y = []
                new_axis_z = []
                new_polygons = []

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
                    if not record:
                        continue

                    hydrate_detection(det, record)
                    is_board = record.get("record_type") == "BOARD"

                    # --- Calibration keypoints for BOARD records ---
                    if is_board and record.get("keypoints"):
                        cal_kps = map_calibration_keypoints(record["keypoints"], width, height)
                        new_calibration_kps.extend(cal_kps)

                        # Track board dimensions for skeleton construction
                        board_def = record.get("board_definition")
                        if board_def and calibration_skeleton_dims is None:
                            bd_rows = board_def.get("rows", 0)
                            bd_cols = board_def.get("cols", 0)
                            if bd_rows > 1 and bd_cols > 1:
                                calibration_skeleton_dims = (bd_rows, bd_cols)

                    # --- Tag corners (skip for BOARD — single center point) ---
                    if "corners" in record and not is_board:
                        pts = get_polyline_points(record["corners"], width, height)
                        det.segmentation = [pts]

                        new_polygons.append(
                            fo.Polyline(
                                label=str(tag_id),
                                points=[pts],
                                closed=True,
                            )
                        )

                        kps = map_corners_to_keypoints(record["corners"], width, height)
                        new_keypoints.extend(kps.keypoints)

                    # --- 3D Axes Overlay (works for both TAGs and BOARDs) ---
                    if "k_matrix" in record and "resolution" in record:
                        axes = project_tag_axes(
                            record,
                            k_matrix=record["k_matrix"],
                            resolution=record["resolution"],
                            distortion_coeffs=record.get("distortion_coeffs") or [],
                            distortion_model=record.get("distortion_model", "none"),
                        )
                        if axes:
                            new_axis_x.append(axes["axis_x"])
                            new_axis_y.append(axes["axis_y"])
                            new_axis_z.append(axes["axis_z"])

                if new_keypoints:
                    sample["corners"] = fo.Keypoints(keypoints=new_keypoints)
                if new_calibration_kps:
                    sample["calibration_points"] = fo.Keypoints(keypoints=new_calibration_kps)
                if new_polygons:
                    sample["polygons"] = fo.Polylines(polylines=new_polygons)
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
        create_saved_views(dataset)
        progress.update(task_views, advance=1)

    # Apply color scheme for axes visualization targeting separate fields
    color_fields = [
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
        {"path": "calibration_points", "fieldColor": "#FF6600"},
    ]

    color_scheme = fo.ColorScheme(
        multicolor_keypoints=True,
        color_pool=["#FF0000", "#00FF00", "#0000FF", "#000000"],
        fields=color_fields,
    )
    dataset.app_config.color_scheme = color_scheme

    # Render edges connecting the corners to visualize the Clockwise (CW) winding order
    skeletons = {
        "corners": fo.KeypointSkeleton(
            labels=["0", "1", "2", "3"], edges=[[0, 1], [1, 2], [2, 3], [3, 0]]
        ),
    }

    # Add calibration grid skeleton if board dimensions were found
    if calibration_skeleton_dims is not None:
        skeletons["calibration_points"] = build_calibration_skeleton(*calibration_skeleton_dims)

    dataset.skeletons.update(skeletons)

    dataset.save()

    session = find_active_session()
    if session:
        print(f"Reusing active FiftyOne session on {session.url}...")
        session.dataset = dataset
    else:
        print(f"Launching FiftyOne App on {address}:{port}...")
        session = fo.launch_app(dataset, address=address, port=port, remote=remote)

    session.wait()
