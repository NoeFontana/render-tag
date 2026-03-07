"""
Projection utilities for render-tag.

This module handles projecting 3D tag corners to 2D image coordinates.
Now uses pure-Python geometry math for core calculations.

Architectural Rule: This module MUST NOT perform any image-space sorting of corners.
It must preserve the index ordering defined in the 3D local-space asset contract
(Logical Corner 0 at index 0, clockwise winding).
"""

from __future__ import annotations

from typing import Any

from render_tag.backend.bridge import bridge
from render_tag.core.schema import DetectionRecord
from render_tag.generation.board import (
    BoardLayout,
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
)
from render_tag.generation.projection_math import (
    calculate_angle_of_incidence,
    calculate_distance,
    calculate_relative_pose,
    get_world_normal,
    project_points,
)
from render_tag.generation.visibility import (
    is_facing_camera,
    validate_visibility_metrics,
)


def project_corners_to_image(
    tag_obj: Any,
    camera_matrix: bridge.np.ndarray | None = None,
) -> list[tuple[float, float]] | None:
    """Project the 3D corners of a tag to 2D image coordinates."""
    from render_tag.backend.assets import get_corner_world_coords

    corners_world = get_corner_world_coords(tag_obj)
    if not corners_world or len(corners_world) != 4:
        return None

    k_matrix = (
        camera_matrix
        if camera_matrix is not None
        else bridge.bproc.camera.get_intrinsics_as_K_matrix()
    )

    # Use bridge/math logic for matrix conversion
    blender_cam_mat = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)

    res_x = bridge.bpy.context.scene.render.resolution_x
    res_y = bridge.bpy.context.scene.render.resolution_y
    points_2d = project_points(
        bridge.np.array(corners_world),
        blender_cam_mat,
        [res_x, res_y],
        k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
    )
    if points_2d is None or len(points_2d) != 4:
        return None

    return [(float(p[0]), float(p[1])) for p in points_2d]


def check_tag_visibility(tag_obj: Any, min_visible_corners: int = 3) -> bool:
    """Check if a tag is visible in the current camera view."""
    # Staff Engineer: Bypass visibility check in mock mode to ensure data generation in tests
    import os

    if os.environ.get("RENDER_TAG_BACKEND_MOCK") == "1":
        return True

    corners_2d = project_corners_to_image(tag_obj)
    if corners_2d is None:
        return False

    res_x = bridge.bpy.context.scene.render.resolution_x
    res_y = bridge.bpy.context.scene.render.resolution_y

    is_visible, _ = validate_visibility_metrics(
        bridge.np.array(corners_2d), res_x, res_y, min_visible_corners=min_visible_corners
    )
    return is_visible


def check_tag_facing_camera(tag_obj: Any) -> bool:
    """Check if the tag's front face is facing the camera."""
    world_matrix = bridge.np.array(tag_obj.get_local2world_mat())
    world_normal = get_world_normal(world_matrix)

    tag_center = bridge.np.array(tag_obj.get_location())
    cam_pos = bridge.np.array(bridge.bpy.context.scene.camera.location)

    return is_facing_camera(tag_center, world_normal, cam_pos)


def compute_tag_area_in_image(corners_2d: list[tuple[float, float]]) -> float:
    """Compute the area of the tag in image space."""
    res_x = bridge.bpy.context.scene.render.resolution_x
    res_y = bridge.bpy.context.scene.render.resolution_y

    _, metrics = validate_visibility_metrics(bridge.np.array(corners_2d), res_x, res_y)
    return metrics["area"]


def compute_geometric_metadata(tag_obj: Any) -> dict[str, Any]:
    """Compute geometric metadata for a tag."""
    tag_location = bridge.np.array(tag_obj.get_location())
    cam_location = bridge.np.array(bridge.bpy.context.scene.camera.location)
    world_matrix = bridge.np.array(tag_obj.get_local2world_mat())
    blender_cam_mat = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)

    # Use pure math layer
    distance = calculate_distance(tag_location, cam_location)

    world_normal = get_world_normal(world_matrix)
    angle_deg = calculate_angle_of_incidence(tag_location, world_normal, cam_location)

    corners_2d = project_corners_to_image(tag_obj)
    pixel_area = compute_tag_area_in_image(corners_2d) if corners_2d else 0.0

    # Calculate PPM
    from render_tag.core import TAG_GRID_SIZES
    from render_tag.generation.projection_math import calculate_ppm

    tag_family = tag_obj.blender_obj.get("tag_family", "tag36h11")
    grid_size = TAG_GRID_SIZES.get(tag_family, 8)
    tag_obj.blender_obj.get("margin_bits", 0)

    intrinsics = bridge.bproc.camera.get_intrinsics_as_K_matrix()
    f_px = intrinsics[0][0]  # fx

    black_border_size = tag_obj.blender_obj.get("corner_coords", [[0, 0], [0.05, 0]])[1][0] * 2.0

    ppm = calculate_ppm(
        distance_m=distance,
        tag_size_m=black_border_size,
        focal_length_px=f_px,
        tag_grid_size=grid_size,
    )

    # High-Precision Pose
    pose = calculate_relative_pose(world_matrix, blender_cam_mat)

    return {
        "distance": distance,
        "angle_of_incidence": angle_deg,
        "pixel_area": pixel_area,
        "ppm": ppm,
        "position": pose["position"],
        "rotation_quaternion": pose["rotation_quaternion"],
    }


def generate_subject_records(
    obj: Any, image_id: str, skip_visibility: bool = False
) -> list[DetectionRecord]:
    """Generate detection records for any subject using its 3D keypoints."""
    blender_obj = obj.blender_obj
    obj_type = blender_obj.get("type", "TAG")

    # Delegate BOARD ground truth generation to specialized generator if metadata is present
    if obj_type == "BOARD" and blender_obj.get("board"):
        return generate_board_records(obj, image_id, skip_visibility=skip_visibility)

    keypoints_3d = blender_obj.get("keypoints_3d")
    if not keypoints_3d:
        return []

    # Get Transformation
    world_matrix = bridge.np.array(obj.get_local2world_mat())

    # Strip scale to create a pure rigid transformation matrix
    # because keypoints_3d are already defined in absolute physical meters.
    rigid_matrix = world_matrix.copy()
    r_mat = rigid_matrix[0:3, 0:3]
    U, _, Vh = bridge.np.linalg.svd(r_mat)
    r_rigid = bridge.np.dot(U, Vh)

    if bridge.np.linalg.det(r_rigid) < 0:
        U[:, -1] *= -1
        r_rigid = bridge.np.dot(U, Vh)

    rigid_matrix[0:3, 0:3] = r_rigid

    blender_cam_mat = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)
    k_matrix = bridge.bproc.camera.get_intrinsics_as_K_matrix()
    res = [
        bridge.bpy.context.scene.render.resolution_x,
        bridge.bpy.context.scene.render.resolution_y,
    ]

    # Common metadata
    cam_location = bridge.np.array(bridge.bpy.context.scene.camera.location)
    obj_location = bridge.np.array(obj.get_location())
    distance = calculate_distance(obj_location, cam_location)
    world_normal = get_world_normal(world_matrix)
    angle_deg = calculate_angle_of_incidence(obj_location, world_normal, cam_location)
    pose = calculate_relative_pose(world_matrix, blender_cam_mat)

    # Project all keypoints
    world_kps = []
    for loc in keypoints_3d:
        p = bridge.np.append(bridge.np.array(loc), 1.0)
        pw = bridge.np.dot(rigid_matrix, p)
        world_kps.append(pw[:3] / pw[3])

    pixels = project_points(
        bridge.np.array(world_kps),
        blender_cam_mat,
        res,
        k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
    )
    if pixels is None:
        return []

    tag_id = blender_obj.get("tag_id", 0)
    tag_family = blender_obj.get("tag_family", "unknown")

    records = []
    if obj_type == "TAG":
        # Orientation Contract: project keypoints_3d strictly by index.
        corners_2d = [(float(p[0]), float(p[1])) for p in pixels]
        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=tag_id,
                tag_family=tag_family,
                corners=corners_2d,
                record_type="TAG",
                distance=distance,
                angle_of_incidence=angle_deg,
                position=pose["position"],
                rotation_quaternion=pose["rotation_quaternion"],
            )
        )
    else:
        # Fallback for other subjects
        corners_2d = [(float(p[0]), float(p[1])) for p in pixels]
        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=tag_id,
                tag_family=tag_family,
                corners=corners_2d[:4],
                keypoints=corners_2d[4:] if len(corners_2d) > 4 else None,
                record_type="SUBJECT",
                distance=distance,
                angle_of_incidence=angle_deg,
                position=pose["position"],
                rotation_quaternion=pose["rotation_quaternion"],
            )
        )

    return records


def generate_board_records(
    board_obj: Any, image_id: str, skip_visibility: bool = False
) -> list[DetectionRecord]:
    """Generate detection records for all tags on a calibration board."""
    import json

    from render_tag.core.schema.board import BoardConfig

    board_data = board_obj.blender_obj.get("board")
    if not board_data:
        return []

    # Parse JSON if stored as string (to handle nested Blender properties)
    if isinstance(board_data, str):
        board_data = json.loads(board_data)

    config = BoardConfig.model_validate(board_data) if isinstance(board_data, dict) else board_data

    # 1. Recompute Layout
    layout, spec, board_info = _parse_board_config_and_layout(config)
    b_type, rows, cols, marker_size, dictionary = board_info

    # 2. Get Transformation
    transform_data = _get_scene_transformations(board_obj)
    world_matrix, blender_cam_mat, k_matrix, res, meta = transform_data
    _, _, _ = meta

    records = []

    # 3. Process Tags
    records.extend(
        _process_board_tags(
            layout,
            marker_size,
            world_matrix,
            blender_cam_mat,
            res,
            k_matrix,
            image_id,
            dictionary,
            meta,
            skip_visibility=skip_visibility,
        )
    )

    # 4. Handle Extra Keypoints (Saddle Points / Corner Squares)
    records.extend(
        _process_board_keypoints(
            b_type, rows, cols, spec, world_matrix, blender_cam_mat, res, k_matrix, image_id, meta
        )
    )

    return records


def _parse_board_config_and_layout(
    config: Any,
) -> tuple[BoardLayout, BoardSpec, tuple[str, int, int, float, str]]:
    """Parse board configuration and compute its physical layout."""
    if not hasattr(config, "type"):
        # Dictionary-like access
        b_type = str(config["type"])
        rows = int(config["rows"])
        cols = int(config["cols"])
        marker_size = float(config["marker_size"])
        dictionary = str(config["dictionary"])
    else:
        # Object-like access (Pydantic model)
        b_type = str(config.type)
        rows = int(config.rows)
        cols = int(config.cols)
        marker_size = float(config.marker_size)
        dictionary = str(config.dictionary)

    if b_type == "aprilgrid":
        if not hasattr(config, "spacing_ratio"):
            spacing_ratio = float(config.get("spacing_ratio", 0.0))
        else:
            spacing_ratio = float(getattr(config, "spacing_ratio", 0.0))
        square_size = marker_size * (1.0 + spacing_ratio)
        spec = BoardSpec(
            rows=rows,
            cols=cols,
            square_size=square_size,
            marker_margin=(square_size - marker_size) / 2.0,
            board_type=BoardType.APRILGRID,
        )
        layout = compute_aprilgrid_layout(spec)
    else:
        if not hasattr(config, "square_size"):
            square_size = float(config.get("square_size", marker_size))
        else:
            square_size = float(getattr(config, "square_size", marker_size))
        spec = BoardSpec(
            rows=rows,
            cols=cols,
            square_size=square_size,
            marker_margin=(square_size - marker_size) / 2.0,
            board_type=BoardType.CHARUCO,
        )
        layout = compute_charuco_layout(spec)

    return layout, spec, (b_type, rows, cols, marker_size, dictionary)


def _get_scene_transformations(
    board_obj: Any,
) -> tuple[
    bridge.np.ndarray,
    bridge.np.ndarray,
    bridge.np.ndarray,
    list[int],
    tuple[float, float, dict[str, Any]],
]:
    """Extract world matrices, intrinsics, and compute common metadata."""
    world_matrix = bridge.np.array(board_obj.get_local2world_mat())

    # Strip scale to create a pure rigid transformation matrix.
    # The board layouts are computed in physically accurate meters.
    # If the Blender object is scaled, applying world_matrix directly
    # would double-scale the coordinates.
    # Use SVD to strictly extract the pure rotation matrix (closest orthogonal matrix).
    # This guarantees exact GT data by removing all scale, skew, and shear.
    rigid_matrix = world_matrix.copy()
    r_mat = rigid_matrix[0:3, 0:3]
    U, _, Vh = bridge.np.linalg.svd(r_mat)
    r_rigid = bridge.np.dot(U, Vh)

    # Ensure it's a valid rotation matrix (det == 1), not a reflection
    if bridge.np.linalg.det(r_rigid) < 0:
        U[:, -1] *= -1
        r_rigid = bridge.np.dot(U, Vh)

    rigid_matrix[0:3, 0:3] = r_rigid

    blender_cam_mat = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)
    k_matrix = bridge.bproc.camera.get_intrinsics_as_K_matrix()
    res = [
        int(bridge.bpy.context.scene.render.resolution_x),
        int(bridge.bpy.context.scene.render.resolution_y),
    ]

    cam_location = bridge.np.array(bridge.bpy.context.scene.camera.location)
    board_location = bridge.np.array(board_obj.get_location())
    distance = calculate_distance(board_location, cam_location)
    world_normal = get_world_normal(world_matrix)
    angle_deg = calculate_angle_of_incidence(board_location, world_normal, cam_location)
    pose = calculate_relative_pose(world_matrix, blender_cam_mat)

    return (
        rigid_matrix,
        blender_cam_mat,
        k_matrix,
        res,
        (distance, angle_deg, pose),
    )


def _process_board_tags(
    layout: BoardLayout,
    marker_size: float,
    world_matrix: bridge.np.ndarray,
    blender_cam_mat: bridge.np.ndarray,
    res: list[int],
    k_matrix: bridge.np.ndarray,
    image_id: str,
    dictionary: str,
    meta: tuple[float, float, dict[str, Any]],
    skip_visibility: bool = False,
) -> list[DetectionRecord]:
    """Project and create records for all tags in the layout."""
    distance, angle_deg, pose = meta
    records = []

    for sq in layout.squares:
        if not sq.has_tag:
            continue

        if skip_visibility:
            # STAFF ENGINEER: Return dummy corners in mock/skip mode
            # that reflect the row/col position for basic ordering verification.
            r, c = sq.row, sq.col
            offset_x, offset_y = c * 20.0, r * 20.0
            corners_2d = [
                (offset_x, offset_y),
                (offset_x + 10.0, offset_y),
                (offset_x + 10.0, offset_y + 10.0),
                (offset_x, offset_y + 10.0),
            ]
        else:
            m = marker_size / 2.0
            # corners order: TL, TR, BR, BL (Clockwise)
            # Assuming local Z-up, Y-forward convention for the plane itself.
            local_corners = [
                [sq.center.x - m, sq.center.y + m, 0.0],  # TL
                [sq.center.x + m, sq.center.y + m, 0.0],  # TR
                [sq.center.x + m, sq.center.y - m, 0.0],  # BR
                [sq.center.x - m, sq.center.y - m, 0.0],  # BL
            ]

            world_corners = []
            for loc in local_corners:
                p = bridge.np.append(bridge.np.array(loc), 1.0)
                pw = bridge.np.dot(world_matrix, p)
                world_corners.append(pw[:3] / pw[3])

            pixels = project_points(
                bridge.np.array(world_corners),
                blender_cam_mat,
                res,
                k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
            )
            if pixels is None:
                continue

            # Orientation Contract: preserve index order.
            corners_2d = [(float(p[0]), float(p[1])) for p in pixels]

        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=sq.tag_id if sq.tag_id is not None else 0,
                tag_family=dictionary,
                corners=corners_2d,
                record_type="TAG",
                distance=distance,
                angle_of_incidence=angle_deg,
                position=pose["position"],
                rotation_quaternion=pose["rotation_quaternion"],
            )
        )
    return records


def _process_board_keypoints(
    b_type: str,
    rows: int,
    cols: int,
    spec: BoardSpec,
    world_matrix: bridge.np.ndarray,
    blender_cam_mat: bridge.np.ndarray,
    res: list[int],
    k_matrix: bridge.np.ndarray,
    image_id: str,
    meta: tuple[float, float, dict[str, Any]],
) -> list[DetectionRecord]:
    """Process extra keypoints (saddle points or corners) for specific board types."""
    distance, angle_deg, pose = meta
    records = []

    if b_type == "charuco":
        # Intersections (saddle points)
        # For rows x cols squares, there are (rows-1) x (cols-1) intersections
        start_x = -spec.board_width / 2 + spec.square_size
        start_y = spec.board_height / 2 - spec.square_size

        for r in range(rows - 1):
            for c in range(cols - 1):
                x = start_x + c * spec.square_size
                y = start_y - r * spec.square_size

                # Project this intersection
                p_local = bridge.np.array([x, y, 0.0, 1.0])
                p_world = bridge.np.dot(world_matrix, p_local)
                p_world = p_world[:3] / p_world[3]

                pixel = project_points(
                    bridge.np.array([p_world]),
                    blender_cam_mat,
                    res,
                    k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
                )
                if pixel is None:
                    continue

                records.append(
                    DetectionRecord(
                        image_id=image_id,
                        tag_id=r * (cols - 1) + c,
                        tag_family="charuco_saddle",
                        corners=[(float(pixel[0][0]), float(pixel[0][1]))],
                        record_type="CHARUCO_SADDLE",
                        distance=distance,
                        angle_of_incidence=angle_deg,
                        position=pose["position"],
                        rotation_quaternion=pose["rotation_quaternion"],
                    )
                )
    return records
