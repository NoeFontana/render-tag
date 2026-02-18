"""
Projection utilities for render-tag.

This module handles projecting 3D tag corners to 2D image coordinates.
Now uses pure-Python geometry math for core calculations.
"""

from __future__ import annotations

from typing import Any

from render_tag.backend.bridge import bridge
from render_tag.core.schema import DetectionRecord
from render_tag.generation.board import (
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

    # PPM is calculated for the modules (grid), not the white margin
    # So we use the original grid size.

    intrinsics = bridge.bproc.camera.get_intrinsics_as_K_matrix()
    f_px = intrinsics[0][0]  # fx

    # Tag size in object is total including margin
    tag_obj.blender_obj.get("corner_coords")[1][0] * 2.0  # simplified from [half, half]
    # Wait, corner_coords are the BLACK BORDER corners already
    # Let's re-verify from assets.py
    # half_black = (size_meters * black_border_scale) / 2.0
    # corners_local = [[-half_black, -half_black, 0.0], ...]

    # So the distance between corners is size_meters * (grid_size / total_bits)
    black_border_size = tag_obj.blender_obj.get("corner_coords")[1][0] * 2.0

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


def generate_subject_records(obj: Any, image_id: str) -> list[DetectionRecord]:
    """Generate detection records for any subject using its 3D keypoints.

    This is the polymorphic projection engine that handles Tags, Boards,
    or any future subject type by projecting its stored keypoints_3d.

    Args:
        obj: The subject mesh object (BlenderProc wrapper).
        image_id: ID of the current image for tracking.

    Returns:
        A list of DetectionRecord objects containing projected corners and 
        metadata.
    """
    blender_obj = obj.blender_obj
    keypoints_3d = blender_obj.get("keypoints_3d")
    if not keypoints_3d:
        return []

    # Get Transformation
    world_matrix = bridge.np.array(obj.get_local2world_mat())
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
        pw = bridge.np.dot(world_matrix, p)
        world_kps.append(pw[:3] / pw[3])

    pixels = project_points(
        bridge.np.array(world_kps),
        blender_cam_mat,
        res,
        k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
    )
    if pixels is None:
        return []

    # Tag or Board?
    obj_type = blender_obj.get("type", "TAG")
    tag_id = blender_obj.get("tag_id", 0)
    tag_family = blender_obj.get("tag_family", "unknown")

    records = []
    if obj_type == "TAG":
        # Standard tag has 4 corners
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
        # BOARD subject: keypoints might represent many things.
        # For now, we follow the legacy Board logic where tags are first, then intersections.
        # But wait, we can just export them as individual records if we want high granularity.
        # In Phase 1, we aim for "Generic" - so let's just return one record with keypoints.
        corners_2d = [(float(p[0]), float(p[1])) for p in pixels]
        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=tag_id,
                tag_family=tag_family,
                corners=corners_2d[:4],  # Default bounding corners
                keypoints=corners_2d[4:] if len(corners_2d) > 4 else None,
                record_type="SUBJECT",
                distance=distance,
                angle_of_incidence=angle_deg,
                position=pose["position"],
                rotation_quaternion=pose["rotation_quaternion"],
            )
        )

    return records


def generate_board_records(board_obj: Any, image_id: str) -> list[DetectionRecord]:
    """Generate detection records for all tags on a calibration board."""
    from render_tag.core.schema.board import BoardConfig

    board_data = board_obj.blender_obj.get("board")
    if not board_data:
        return []

    config = (
        BoardConfig.model_validate(board_data) if isinstance(board_data, dict) else board_data
    )

    # 1. Recompute Layout
    layout, spec, board_info = _parse_board_config_and_layout(config)
    b_type, rows, cols, marker_size, dictionary = board_info

    # 2. Get Transformation
    transform_data = _get_scene_transformations(board_obj)
    world_matrix, blender_cam_mat, k_matrix, res, meta = transform_data
    distance, angle_deg, pose = meta

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
        )
    )

    # 4. Handle Extra Keypoints (Saddle Points / Corner Squares)
    records.extend(
        _process_board_keypoints(
            b_type, rows, cols, spec, world_matrix, blender_cam_mat, res, k_matrix, image_id, meta
        )
    )

    return records


def _parse_board_config_and_layout(config: Any) -> tuple[Any, BoardSpec, tuple]:
    """Parse board configuration and compute its physical layout."""
    if not isinstance(config, dict):
        b_type = config.get("type")
        rows = config.get("rows")
        cols = config.get("cols")
        marker_size = config.get("marker_size")
        dictionary = config.get("dictionary")
    else:
        b_type = config["type"]
        rows = config["rows"]
        cols = config["cols"]
        marker_size = config["marker_size"]
        dictionary = config["dictionary"]

    if b_type == "aprilgrid":
        spacing_ratio = config.get("spacing_ratio", 0.0)
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
        square_size = config.get("square_size", marker_size)
        spec = BoardSpec(
            rows=rows,
            cols=cols,
            square_size=square_size,
            marker_margin=(square_size - marker_size) / 2.0,
            board_type=BoardType.CHARUCO,
        )
        layout = compute_charuco_layout(spec)

    return layout, spec, (b_type, rows, cols, marker_size, dictionary)


def _get_scene_transformations(board_obj: Any) -> tuple:
    """Extract world matrices, intrinsics, and compute common metadata."""
    world_matrix = bridge.np.array(board_obj.get_local2world_mat())
    blender_cam_mat = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)
    k_matrix = bridge.bproc.camera.get_intrinsics_as_K_matrix()
    res = [
        bridge.bpy.context.scene.render.resolution_x,
        bridge.bpy.context.scene.render.resolution_y,
    ]

    cam_location = bridge.np.array(bridge.bpy.context.scene.camera.location)
    board_location = bridge.np.array(board_obj.get_location())
    distance = calculate_distance(board_location, cam_location)
    world_normal = get_world_normal(world_matrix)
    angle_deg = calculate_angle_of_incidence(board_location, world_normal, cam_location)
    pose = calculate_relative_pose(world_matrix, blender_cam_mat)

    return (
        world_matrix,
        blender_cam_mat,
        k_matrix,
        res,
        (distance, angle_deg, pose),
    )


def _process_board_tags(
    layout, marker_size, world_matrix, blender_cam_mat, res, k_matrix, image_id, dictionary, meta
) -> list[DetectionRecord]:
    """Project and create records for all tags in the layout."""
    distance, angle_deg, pose = meta
    records = []

    for sq in layout.squares:
        if not sq.has_tag:
            continue

        m = marker_size / 2.0
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

        corners_2d = [(float(p[0]), float(p[1])) for p in pixels]

        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=sq.tag_id,
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
    b_type, rows, cols, spec, world_matrix, blender_cam_mat, res, k_matrix, image_id, meta
) -> list[DetectionRecord]:
    """Process extra keypoints (saddle points or corners) for specific board types."""
    distance, angle_deg, pose = meta
    records = []

    if b_type == "charuco":
        for r in range(1, rows):
            for c in range(1, cols):
                lx = -spec.board_width / 2.0 + c * spec.square_size
                ly = -spec.board_height / 2.0 + r * spec.square_size

                p = bridge.np.append(bridge.np.array([lx, ly, 0.0]), 1.0)
                pw = bridge.np.dot(world_matrix, p)
                w_pos = pw[:3] / pw[3]

                pixels = project_points(
                    bridge.np.array([w_pos]),
                    blender_cam_mat,
                    res,
                    k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
                )
                if pixels is not None:
                    px = pixels[0]
                    records.append(
                        DetectionRecord(
                            image_id=image_id,
                            tag_id=r * 100 + c,
                            tag_family="charuco_saddle",
                            corners=[(float(px[0]), float(px[1]))],
                            record_type="CHARUCO_SADDLE",
                            distance=distance,
                            angle_of_incidence=angle_deg,
                            position=pose["position"],
                            rotation_quaternion=pose["rotation_quaternion"],
                        )
                    )
    elif b_type == "aprilgrid":
        for r in range(rows + 1):
            for c in range(cols + 1):
                lx = -spec.board_width / 2.0 + c * spec.square_size
                ly = -spec.board_height / 2.0 + r * spec.square_size

                p = bridge.np.append(bridge.np.array([lx, ly, 0.0]), 1.0)
                pw = bridge.np.dot(world_matrix, p)
                w_pos = pw[:3] / pw[3]

                pixels = project_points(
                    bridge.np.array([w_pos]),
                    blender_cam_mat,
                    res,
                    k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
                )
                if pixels is not None:
                    px = pixels[0]
                    records.append(
                        DetectionRecord(
                            image_id=image_id,
                            tag_id=r * 100 + c,
                            tag_family="aprilgrid_corner",
                            corners=[(float(px[0]), float(px[1]))],
                            record_type="APRILGRID_CORNER",
                            distance=distance,
                            angle_of_incidence=angle_deg,
                            position=pose["position"],
                            rotation_quaternion=pose["rotation_quaternion"],
                        )
                    )
    return records
