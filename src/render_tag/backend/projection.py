"""
Projection utilities for render-tag.

This module handles projecting 3D tag corners to 2D image coordinates.
Now uses pure-Python geometry math for core calculations.

Architectural Rule: This module MUST NOT perform any image-space sorting of corners.
It must preserve the index ordering defined in the 3D local-space asset contract
(Logical Corner 0 at index 0, clockwise winding).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from render_tag.core.schema.recipe import CameraRecipe

from render_tag.backend.bridge import bridge
from render_tag.core import TAG_GRID_SIZES
from render_tag.core.schema import DetectionRecord
from render_tag.core.schema.base import KEYPOINT_SENTINEL
from render_tag.core.schema.board import BoardConfig, BoardDefinition
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
    calculate_ppm,
    calculate_relative_pose,
    get_world_normal,
    project_points,
    sanitize_to_rigid_transform,
)
from render_tag.generation.visibility import (
    is_facing_camera,
    validate_visibility_metrics,
)


def _get_corrected_k_matrix() -> bridge.np.ndarray:
    """Get the K matrix from BlenderProc and correct its principal point to continuous coords."""
    k = bridge.bproc.camera.get_intrinsics_as_K_matrix()
    # Staff Engineer: BlenderProc's `get_intrinsics_as_K_matrix` reconstructs the principal point
    # using the legacy `(W - 1) / 2` convention. Because we forcefully centered the physical
    # sensor by passing `W/2 - 0.5` during setup, BlenderProc returns `(W - 1) / 2` here.
    # We must add 0.5 back to restore the strictly continuous OpenCV coordinates (W/2.0, H/2.0)
    # required for perfect mathematical projection without a half-pixel bias.
    k[0][2] += 0.5
    k[1][2] += 0.5
    return k


def project_corners_to_image(
    tag_obj: Any,
    camera_matrix: bridge.np.ndarray | None = None,
) -> list[tuple[float, float]] | None:
    """Project the 3D corners of a tag to 2D image coordinates."""
    from render_tag.backend.assets import get_corner_world_coords

    corners_world = get_corner_world_coords(tag_obj)
    if not corners_world or len(corners_world) != 4:
        return None

    k_matrix = camera_matrix if camera_matrix is not None else _get_corrected_k_matrix()

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

    # Respect custom forward axis for non-Z-up assets
    local_normal = tag_obj.blender_obj.get("forward_axis")
    if local_normal:
        local_normal = bridge.np.array(local_normal)

    world_normal = get_world_normal(world_matrix, local_normal=local_normal)

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
    tag_family = tag_obj.blender_obj.get("tag_family", "tag36h11")
    grid_size = TAG_GRID_SIZES.get(tag_family, 8)

    intrinsics = _get_corrected_k_matrix()
    f_px = intrinsics[0][0]  # fx

    # Calculate the physical width of the active black border from keypoints_3d.
    # keypoints_3d[0]=TL, keypoints_3d[1]=TR in local [-1,1] space, inset by margin_bits.
    # The physical size is local_width * scale_norm (X column of the world matrix).
    norms = bridge.np.linalg.norm(world_matrix[:3, :3], axis=0)
    keypoints_3d = tag_obj.blender_obj.get("keypoints_3d")
    if keypoints_3d and len(keypoints_3d) >= 2:
        tl = bridge.np.array(keypoints_3d[0])
        tr = bridge.np.array(keypoints_3d[1])
        local_width = float(bridge.np.linalg.norm(tr[:2] - tl[:2]))
        black_border_size = local_width * float(norms[0])
    else:
        black_border_size = float(norms[0]) * 2.0  # Full plane width as fallback

    # Calculate orthogonal Z-depth (distance along camera's forward axis)
    # Camera forward in Blender is -Z.
    cam_world_matrix = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)
    cam_forward_world = -cam_world_matrix[:3, 2]  # Third column is Z, negate for forward

    vec_cam_tag = tag_location - cam_location
    z_depth = bridge.np.dot(vec_cam_tag, cam_forward_world)

    ppm = calculate_ppm(
        z_depth_m=float(z_depth),
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


def _extract_physics(cam_recipe: CameraRecipe | None) -> dict[str, Any]:
    """Extract physics and sensor conditions from a camera recipe."""
    physics = {
        "velocity": None,
        "shutter_time_ms": 0.0,
        "rolling_shutter_ms": 0.0,
        "fstop": None,
    }

    if cam_recipe:
        dynamics = cam_recipe.sensor_dynamics
        if dynamics:
            physics["velocity"] = dynamics.velocity
            physics["shutter_time_ms"] = dynamics.shutter_time_ms or 0.0
            physics["rolling_shutter_ms"] = dynamics.rolling_shutter_duration_ms or 0.0
        physics["fstop"] = cam_recipe.fstop

    return physics


def _extract_distortion(
    cam_recipe: CameraRecipe | None,
) -> tuple[list[float] | None, str]:
    """Return (distortion_coeffs, distortion_model) from a recipe, or (None, 'none')."""
    if cam_recipe is not None:
        return (
            cam_recipe.intrinsics.distortion_coeffs or None,
            cam_recipe.intrinsics.distortion_model,
        )
    return None, "none"


def generate_subject_records(
    obj: Any,
    image_id: str,
    cam_recipe: CameraRecipe | None = None,
    skip_visibility: bool = False,
) -> list[DetectionRecord]:
    """Generate detection records for any subject using its 3D keypoints."""
    blender_obj = obj.blender_obj
    obj_type = blender_obj.get("type", "TAG")

    # Delegate BOARD ground truth generation to specialized generator if metadata is present
    if obj_type == "BOARD" and blender_obj.get("board"):
        return generate_board_records(
            obj, image_id, cam_recipe=cam_recipe, skip_visibility=skip_visibility
        )

    keypoints_3d = blender_obj.get("keypoints_3d")
    if not keypoints_3d:
        return []

    # Get Transformation
    raw_world_mat = obj.get_local2world_mat()
    raw_world_matrix = bridge.np.array(raw_world_mat) if raw_world_mat is not None else None

    # Defensive check for unit-testing mocks
    if raw_world_matrix is None or raw_world_matrix.ndim != 2 or raw_world_matrix.shape != (4, 4):
        raw_world_matrix = bridge.np.eye(4)

    world_matrix, is_mirrored = sanitize_to_rigid_transform(
        raw_world_matrix, return_is_mirrored=True
    )

    norms = bridge.np.linalg.norm(raw_world_matrix[:3, :3], axis=0)

    # Domain Validation: Enforce strict geometric invariants for tags
    if obj_type == "TAG" and not bridge.np.isclose(norms[0], norms[1], rtol=1e-2):
        raise ValueError(
            f"Fiducial TAGs must be perfectly square. "
            f"Detected non-uniform scale (X:{norms[0]:.3f} vs Y:{norms[1]:.3f})."
        )

    blender_cam_mat = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)

    # Prefer recipe intrinsics over Blender state: when distortion is active,
    # Blender is configured with the overscan K-matrix, so we must use the
    # target K (and target resolution) for all annotation coordinates.
    if cam_recipe is not None:
        k_list: list[list[float]] = cam_recipe.intrinsics.k_matrix
        res: list[int] = cam_recipe.intrinsics.resolution
    else:
        k_raw = _get_corrected_k_matrix()
        k_list = k_raw.tolist() if hasattr(k_raw, "tolist") else k_raw
        res = [
            bridge.bpy.context.scene.render.resolution_x,
            bridge.bpy.context.scene.render.resolution_y,
        ]
    dist_coeffs, dist_model = _extract_distortion(cam_recipe)

    # Common metadata
    cam_location = bridge.np.array(bridge.bpy.context.scene.camera.location)
    obj_location = bridge.np.array(obj.get_location())
    distance = calculate_distance(obj_location, cam_location)
    world_normal = get_world_normal(world_matrix)
    angle_deg = calculate_angle_of_incidence(obj_location, world_normal, cam_location)

    # Center-Origin Convention: Pose is anchored at the geometric center of the marker.
    # This matches the native behavior of AprilTag, ArUco, and locus-tag detectors.
    pose = calculate_relative_pose(world_matrix, blender_cam_mat)

    # Physics Metadata
    physics = _extract_physics(cam_recipe)

    # Project all keypoints (absorbing the exact scale element-wise)
    world_kps = []
    for loc in keypoints_3d:
        p_local = bridge.np.array(loc) * norms
        p = bridge.np.append(p_local, 1.0)
        pw = bridge.np.dot(world_matrix, p)
        world_kps.append(pw[:3] / pw[3])

    pixels = project_points(
        bridge.np.array(world_kps),
        blender_cam_mat,
        res,
        k_list,
        distortion_coeffs=dist_coeffs,
        distortion_model=dist_model,
    )
    if pixels is None:
        return []

    tag_id = blender_obj.get("tag_id", 0)
    tag_family = blender_obj.get("tag_family", "unknown")

    # Calculate tag_size_mm (active black-to-black size)
    grid_size = TAG_GRID_SIZES.get(tag_family, 8)
    margin_bits = blender_obj.get("margin_bits", 0)
    total_bits = grid_size + 2 * margin_bits

    # The Blender primitive is a 2x2 plane [-1, 1]. Total size in meters is exactly scale * 2.
    if obj_type == "TAG":
        total_size_m = float(norms[0]) * 2.0
    else:
        total_size_m = float(bridge.np.mean(norms[:2])) * 2.0

    active_size_mm = (total_size_m * 1000.0 * grid_size) / total_bits

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
                tag_size_mm=float(active_size_mm),
                k_matrix=k_list,
                resolution=res,
                distortion_model=dist_model,
                distortion_coeffs=dist_coeffs or [],
                velocity=physics["velocity"],
                shutter_time_ms=physics["shutter_time_ms"],
                rolling_shutter_ms=physics["rolling_shutter_ms"],
                fstop=physics["fstop"],
                eval_margin_px=cam_recipe.intrinsics.eval_margin_px if cam_recipe else 0,
                is_mirrored=is_mirrored,
            )
        )
    else:
        # Fallback for other subjects
        corners_2d = [(float(p[0]), float(p[1])) for p in pixels]

        # Defensive check: DetectionRecord validator expects 4 corners for CW check.
        # If we have exactly 4, we assume they are corners.
        # If we have more, we split them.
        # If we have less, we put all in 'corners' (COCOWriter/CSVWriter handle this).
        if len(corners_2d) > 4:
            c_pts = corners_2d[:4]
            k_pts = corners_2d[4:]
        else:
            c_pts = corners_2d
            k_pts = None

        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=tag_id,
                tag_family=tag_family,
                corners=c_pts,
                keypoints=k_pts,
                record_type="SUBJECT",
                distance=distance,
                angle_of_incidence=angle_deg,
                position=pose["position"],
                rotation_quaternion=pose["rotation_quaternion"],
                tag_size_mm=float(active_size_mm),
                k_matrix=k_list,
                resolution=res,
                distortion_model=dist_model,
                distortion_coeffs=dist_coeffs or [],
                velocity=physics["velocity"],
                shutter_time_ms=physics["shutter_time_ms"],
                rolling_shutter_ms=physics["rolling_shutter_ms"],
                fstop=physics["fstop"],
                eval_margin_px=cam_recipe.intrinsics.eval_margin_px if cam_recipe else 0,
                is_mirrored=is_mirrored,
            )
        )

    return records


def generate_board_records(
    board_obj: Any,
    image_id: str,
    cam_recipe: CameraRecipe | None = None,
    skip_visibility: bool = False,
) -> list[DetectionRecord]:
    """Generate detection records for all tags on a calibration board."""
    board_data = board_obj.blender_obj.get("board")
    if not board_data:
        return []

    # Parse JSON if stored as string (to handle nested Blender properties)
    if isinstance(board_data, str):
        board_data = json.loads(board_data)

    config = BoardConfig.model_validate(board_data) if isinstance(board_data, dict) else board_data

    layout_init, spec_init, info_init = _parse_board_config_and_layout(config)

    # 1. Extract Scale and Recompute Layout
    # Staff Engineer: We must account for Blender object-level scaling by 'absorbing' it
    # into the physical metrics. This allows us to maintain the invariant that the
    # world_matrix used for projection and pose is a pure SE(3) rigid transform.
    raw_world_mat = board_obj.get_local2world_mat()
    raw_mat = bridge.np.array(raw_world_mat) if raw_world_mat is not None else None

    # Defensive check for unit-testing mocks
    if raw_mat is None or raw_mat.ndim != 2 or raw_mat.shape != (4, 4):
        raw_mat = bridge.np.eye(4)

    norms = bridge.np.linalg.norm(raw_mat[:3, :3], axis=0)

    # Calculate user-applied scale by comparing current scale to canonical shape scale
    # Staff Engineer: The Blender mesh is created from a 2x2 plane (-1 to 1)
    # and scaled by (width/2, height/2). persist_transformation_into_mesh()
    # bakes this in, meaning the vertices now literally span [-width/2, width/2].
    # Thus, the base 'canonical' scale of the resulting object is (1.0, 1.0, 1.0).
    # Any user-applied scale in the ObjectRecipe will appear directly in the norms.
    canonical_sx = spec_init.board_width / 2.0
    canonical_sy = spec_init.board_height / 2.0

    # If the generator uses Object-Level scaling (scale=[w/2, h/2]) INSTEAD of
    # bakes, we must detect which mode is active.
    # Case A: Local vertices are [-1, 1], Matrix Scale is [w/2, h/2].
    # Case B: Local vertices are [-w/2, w/2], Matrix Scale is [1, 1].

    # We check if the norms are closer to 1.0 or the canonical half-dims.
    if bridge.np.isclose(norms[0], canonical_sx, rtol=1e-2):
        # Case A: Matrix Scale contains the board dimensions
        user_scale_x = norms[0] / canonical_sx
        user_scale_y = norms[1] / canonical_sy
    else:
        # Case B: Matrix Scale is pure user-applied scale (mesh is baked)
        user_scale_x = norms[0]
        user_scale_y = norms[1]

    # Fiducial boards can be rectangular, but the USER scale applied to them MUST be uniform
    # to prevent square markers from becoming rectangles.
    if not bridge.np.isclose(user_scale_x, user_scale_y, rtol=1e-2):
        raise ValueError(
            f"Fiducial BOARDs cannot be stretched non-uniformly. "
            f"Detected user scale X:{user_scale_x:.3f} vs Y:{user_scale_y:.3f}."
        )
    user_scale = float(user_scale_x)

    if not bridge.np.isclose(user_scale, 1.0, rtol=1e-4):
        if hasattr(config, "model_copy"):
            # Pydantic model
            update = {"marker_size": config.marker_size * user_scale}
            sq_size = getattr(config, "square_size", None)
            if sq_size is not None:
                update["square_size"] = sq_size * user_scale
            config = config.model_copy(update=update)
        elif isinstance(config, dict):
            config = config.copy()
            config["marker_size"] = config.get("marker_size", 0.1) * user_scale
            if config.get("square_size") is not None:
                config["square_size"] = config["square_size"] * user_scale

        layout, spec, board_info = _parse_board_config_and_layout(config)
    else:
        layout, spec, board_info = layout_init, spec_init, info_init

    b_type, rows, cols, marker_size, dictionary = board_info

    # 2. Get Transformation (NOW RIGID/SANITIZED, anchored at Center)
    transform_data = _get_scene_transformations(board_obj, spec, cam_recipe=cam_recipe)
    world_matrix, blender_cam_mat, k_matrix, res, meta = transform_data
    records = []

    dist_coeffs, dist_model = _extract_distortion(cam_recipe)

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
            dist_coeffs=dist_coeffs,
            dist_model=dist_model,
            cam_recipe=cam_recipe,
        )
    )

    # 4. Handle Extra Keypoints (Saddle Points / Corner Squares)
    calibration_points_2d = []
    calib_pts_3d = board_obj.blender_obj.get("calibration_points_3d")

    if calib_pts_3d:
        # Project normalized calibration points from the ObjectRecipe
        for pt in calib_pts_3d:
            # pt is [x, y, 0.0] in physical meters relative to the board center.
            # world_matrix is sanitized (column norms = 1), so this is a pure
            # rotation + translation into world space.
            # Convert to homogeneous and multiply by world matrix
            local_homo = bridge.np.array([pt[0], pt[1], pt[2], 1.0])
            world_homo = bridge.np.dot(world_matrix, local_homo)
            world_pos = (
                world_homo[:3] / world_homo[3] if abs(world_homo[3]) > 1e-6 else world_homo[:3]
            )

            pixel = project_points(
                bridge.np.array([world_pos]),
                blender_cam_mat,
                res,
                k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
                distortion_coeffs=dist_coeffs,
                distortion_model=dist_model,
            )
            calibration_points_2d.append(_project_calibration_point(pixel, res, skip_visibility))
    elif b_type == "charuco":
        # Fallback for old recipes without calibration_points_3d
        start_x = -spec.board_width / 2 + spec.square_size
        start_y = spec.board_height / 2 - spec.square_size

        for r in range(rows - 1):
            for c in range(cols - 1):
                x = start_x + c * spec.square_size
                y = start_y - r * spec.square_size

                local_mat = bridge.np.eye(4)
                local_mat[0, 3] = x
                local_mat[1, 3] = y
                kp_world_matrix = world_matrix @ local_mat
                kp_location = kp_world_matrix[:3, 3]

                pixel = project_points(
                    bridge.np.array([kp_location]),
                    blender_cam_mat,
                    res,
                    k_matrix.tolist() if hasattr(k_matrix, "tolist") else k_matrix,
                    distortion_coeffs=dist_coeffs,
                    distortion_model=dist_model,
                )
                calibration_points_2d.append(
                    _project_calibration_point(pixel, res, skip_visibility)
                )

    # 5. Add Board-Level Metadata Record
    distance, angle_deg, board_pose, physics, _, _, is_mirrored = meta
    board_center_world = world_matrix[:3, 3]
    board_center_pixel = project_points(
        bridge.np.array([board_center_world]),
        blender_cam_mat,
        res,
        k_matrix,
        distortion_coeffs=dist_coeffs,
        distortion_model=dist_model,
    )

    if board_center_pixel is not None:
        # Build typed board_definition for downstream OpenCV/Kalibr consumers
        total_kp = (
            (rows - 1) * (cols - 1) if b_type == "charuco" else len(layout.calibration_positions)
        )
        sr: float | None = None
        if b_type == "aprilgrid":
            # Extract spacing_ratio
            sr = getattr(config, "spacing_ratio", None)
            if sr is None and isinstance(config, dict):
                sr = config.get("spacing_ratio")
            if sr is not None:
                sr = float(sr)

        board_def = BoardDefinition(
            type=b_type,
            rows=rows,
            cols=cols,
            square_size_mm=round(float(spec.square_size * 1000.0), 4),
            marker_size_mm=round(float(marker_size * 1000.0), 4),
            dictionary=dictionary,
            total_keypoints=total_kp,
            spacing_ratio=sr,
        )

        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=-1,  # Special ID for board center
                tag_family=f"board_{b_type}",
                corners=[(float(board_center_pixel[0][0]), float(board_center_pixel[0][1]))],
                keypoints=calibration_points_2d if calibration_points_2d else None,
                record_type="BOARD",
                distance=float(distance),
                angle_of_incidence=float(angle_deg),
                position=board_pose["position"],
                rotation_quaternion=board_pose["rotation_quaternion"],
                tag_size_mm=float(spec.board_width * 1000.0),
                k_matrix=k_matrix,
                resolution=res,
                distortion_model=dist_model,
                distortion_coeffs=dist_coeffs or [],
                velocity=physics["velocity"],
                shutter_time_ms=physics["shutter_time_ms"],
                rolling_shutter_ms=physics["rolling_shutter_ms"],
                fstop=physics["fstop"],
                eval_margin_px=cam_recipe.intrinsics.eval_margin_px if cam_recipe else 0,
                is_mirrored=is_mirrored,
                board_definition=board_def,
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
    spec: BoardSpec,
    cam_recipe: CameraRecipe | None = None,
) -> tuple[
    bridge.np.ndarray,
    bridge.np.ndarray,
    bridge.np.ndarray,
    list[int],
    tuple[float, float, dict[str, Any], dict[str, Any], bridge.np.ndarray, bridge.np.ndarray, bool],
]:
    """Extract world matrices, intrinsics, and compute common metadata."""
    raw_world_matrix = bridge.np.array(board_obj.get_local2world_mat())
    world_matrix, is_mirrored = sanitize_to_rigid_transform(
        raw_world_matrix, return_is_mirrored=True
    )

    blender_cam_mat = bridge.np.array(bridge.bpy.context.scene.camera.matrix_world)

    # Prefer recipe intrinsics: when distortion is active, Blender is at overscan
    # resolution, so we must use the target K and resolution for annotation coords.
    if cam_recipe is not None:
        k_list = cam_recipe.intrinsics.k_matrix
        res = cam_recipe.intrinsics.resolution
    else:
        k_raw = _get_corrected_k_matrix()
        k_list = k_raw.tolist() if hasattr(k_raw, "tolist") else k_raw
        res = [
            int(bridge.bpy.context.scene.render.resolution_x),
            int(bridge.bpy.context.scene.render.resolution_y),
        ]

    cam_location = bridge.np.array(bridge.bpy.context.scene.camera.location)
    board_location = bridge.np.array(board_obj.get_location())
    distance = calculate_distance(board_location, cam_location)
    world_normal = get_world_normal(world_matrix)
    angle_deg = calculate_angle_of_incidence(board_location, world_normal, cam_location)

    # Center-Origin Convention: Pose anchored at the geometric center of the board.
    pose = calculate_relative_pose(world_matrix, blender_cam_mat)

    # Physics Metadata
    physics = _extract_physics(cam_recipe)

    return (
        world_matrix,
        blender_cam_mat,
        k_list,
        res,
        (distance, angle_deg, pose, physics, cam_location, world_normal, is_mirrored),
    )


def _project_calibration_point(
    pixel: bridge.np.ndarray | None,
    res: list[int],
    skip_visibility: bool,
) -> tuple[float, float]:
    """Return projected (u, v) or sentinel (-1, -1) for out-of-frame points.

    Sentinels preserve index alignment so ``keypoints[i]`` always corresponds
    to ``charuco_id == i`` (or the equivalent AprilGrid corner index).
    """
    if pixel is None:
        return KEYPOINT_SENTINEL
    u, v = float(pixel[0][0]), float(pixel[0][1])
    if skip_visibility or (0 <= u < res[0] and 0 <= v < res[1]):
        return (u, v)
    return KEYPOINT_SENTINEL


def _process_board_tags(
    layout: BoardLayout,
    marker_size: float,
    world_matrix: bridge.np.ndarray,
    blender_cam_mat: bridge.np.ndarray,
    res: list[int],
    k_matrix: bridge.np.ndarray,
    image_id: str,
    dictionary: str,
    meta: tuple[
        float, float, dict[str, Any], dict[str, Any], bridge.np.ndarray, bridge.np.ndarray, bool
    ],
    skip_visibility: bool = False,
    dist_coeffs: list[float] | None = None,
    dist_model: str = "none",
    cam_recipe: CameraRecipe | None = None,
) -> list[DetectionRecord]:
    """Project and create records for all tags in the layout."""
    _, _, _, physics, cam_location, world_normal, is_mirrored = meta
    records = []

    for sq in layout.squares:
        if not sq.has_tag:
            continue

        # 1. Compute Unique Tag Transform (Local Translation)
        # Staff Engineer: We apply the procedural offset of the specific tag
        # relative to the board origin to establish its true localized matrix.
        local_mat = bridge.np.eye(4)
        local_mat[0, 3] = sq.center.x
        local_mat[1, 3] = sq.center.y
        tag_world_matrix = world_matrix @ local_mat
        tag_location = tag_world_matrix[:3, 3]

        # 2. Project all corners via the localized matrix
        m = marker_size / 2.0
        # corners order in tag-local: TL, TR, BR, BL (Clockwise)
        tag_local_corners = [
            [-m, m, 0.0, 1.0],  # TL
            [m, m, 0.0, 1.0],  # TR
            [m, -m, 0.0, 1.0],  # BR
            [-m, -m, 0.0, 1.0],  # BL
        ]
        world_corners = [(tag_world_matrix @ p)[:3] for p in tag_local_corners]

        corners_2d_raw = project_points(
            bridge.np.array(world_corners),
            blender_cam_mat,
            res,
            k_matrix,
            distortion_coeffs=dist_coeffs,
            distortion_model=dist_model,
        )

        if corners_2d_raw is None:
            continue

        corners_2d = [(float(p[0]), float(p[1])) for p in corners_2d_raw]

        if not skip_visibility:
            if not is_facing_camera(tag_location, world_normal, cam_location):
                continue
            # Frustum bounds check — all 4 corners must be in-frame (detector contract)
            is_visible, _ = validate_visibility_metrics(
                corners_2d_raw, res[0], res[1], min_visible_corners=4
            )
            if not is_visible:
                continue

        # 3. Calculate Independent Metadata
        # Center-Origin Convention: Pose anchored at the geometric center of the tag.
        tag_pose = calculate_relative_pose(tag_world_matrix, blender_cam_mat)

        records.append(
            DetectionRecord(
                image_id=image_id,
                tag_id=sq.tag_id if sq.tag_id is not None else 0,
                tag_family=dictionary,
                corners=corners_2d,
                record_type="TAG",
                distance=float(calculate_distance(tag_location, cam_location)),
                angle_of_incidence=calculate_angle_of_incidence(
                    tag_location, world_normal, cam_location
                ),
                position=tag_pose["position"],
                rotation_quaternion=tag_pose["rotation_quaternion"],
                tag_size_mm=float(marker_size * 1000.0),
                k_matrix=k_matrix,
                resolution=res,
                distortion_model=dist_model,
                distortion_coeffs=dist_coeffs or [],
                velocity=physics["velocity"],
                shutter_time_ms=physics["shutter_time_ms"],
                rolling_shutter_ms=physics["rolling_shutter_ms"],
                fstop=physics["fstop"],
                eval_margin_px=cam_recipe.intrinsics.eval_margin_px if cam_recipe else 0,
                is_mirrored=is_mirrored,
            )
        )
    return records
