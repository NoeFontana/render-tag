"""Unit tests for OccluderStrategy: half-plane plate placement and shadow geometry."""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from render_tag.cli.pipeline import GenerationContext
from render_tag.core.config import DirectionalLightConfig, GenConfig
from render_tag.core.geometry.math import sun_unit_vector
from render_tag.core.schema.recipe import CameraIntrinsics, CameraRecipe
from render_tag.core.schema.subject import OccluderConfig
from render_tag.generation.strategy.occluder import OccluderStrategy


def _ctx_with_sun(azimuth: float, elevation: float, intensity: float = 30.0) -> GenerationContext:
    ctx = MagicMock(spec=GenerationContext)
    ctx.gen_config = GenConfig()
    ctx.gen_config.scene.lighting.directional = [
        DirectionalLightConfig(azimuth=azimuth, elevation=elevation, intensity=intensity)
    ]
    ctx.output_dir = Path("output")
    return ctx


def _shadow_xy(plate_loc: list[float], sun_dir: tuple[float, float, float]) -> tuple[float, float]:
    """Project a horizontal plate centroid onto z=0 along the SUN ray."""
    sx, sy, sz = sun_dir
    h = plate_loc[2]
    return (plate_loc[0] - h * sx / sz, plate_loc[1] - h * sy / sz)


def _mock_cam(
    location: tuple[float, float, float],
    res: tuple[int, int] = (640, 480),
    fov: float = 90.0
) -> CameraRecipe:
    """Create a CameraRecipe pointing at the origin from a given location."""
    # Build a simple look-at matrix
    loc = np.array(location)
    forward = -loc / np.linalg.norm(loc)
    up = np.array([0, 0, 1])
    if abs(np.dot(forward, up)) > 0.99:
        up = np.array([0, 1, 0])

    right = np.cross(up, forward)
    right /= np.linalg.norm(right)
    actual_up = np.cross(forward, right)

    # transform_matrix is Camera-to-World (X=right, Y=up, Z=-forward)
    mat = np.eye(4)
    mat[:3, 0] = right
    mat[:3, 1] = actual_up
    mat[:3, 2] = -forward
    mat[:3, 3] = loc

    # K matrix from FOV
    f = (res[0] / 2.0) / math.tan(math.radians(fov) / 2.0)
    k = [[f, 0, res[0] / 2.0], [0, f, res[1] / 2.0], [0, 0, 1]]

    return CameraRecipe(
        transform_matrix=mat.tolist(),
        intrinsics=CameraIntrinsics(
            resolution=list(res),
            k_matrix=k,
            fov=fov
        )
    )


def test_disabled_returns_empty():
    cfg = OccluderConfig(enabled=False)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    assert strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)]) == []


def test_no_tag_positions_returns_empty():
    cfg = OccluderConfig(enabled=True)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    assert strategy.sample_pose(seed=42, context=ctx, tag_positions=[]) == []


def test_no_sun_returns_empty():
    cfg = OccluderConfig(enabled=True)
    strategy = OccluderStrategy(cfg)
    ctx = MagicMock(spec=GenerationContext)
    ctx.gen_config = GenConfig()
    ctx.gen_config.scene.lighting.directional = []
    ctx.output_dir = Path("output")
    assert strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)]) == []


def test_zero_elevation_returns_empty():
    """Sun at the horizon would shoot infinite shadows — strategy should bail."""
    cfg = OccluderConfig(enabled=True)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.0, elevation=0.0)
    assert strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)]) == []


def test_half_pattern_emits_single_plate():
    cfg = OccluderConfig(patterns=["half"], edge_offset_max_r=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(out) == 1
    assert out[0].type == "OCCLUDER"
    assert out[0].properties["shape"] == "plate"


def test_corner_pattern_emits_single_quadrant_plate():
    cfg = OccluderConfig(patterns=["corner"], edge_offset_max_r=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(out) == 1


def test_slit_pattern_emits_two_parallel_plates():
    cfg = OccluderConfig(patterns=["slit"], edge_offset_max_r=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(out) == 2
    assert out[0].rotation_euler is not None
    assert out[1].rotation_euler is not None
    assert math.isclose(out[0].rotation_euler[2], out[1].rotation_euler[2], abs_tol=1e-9)


def test_shadow_edge_passes_through_target_for_half_pattern():
    """Plate edge anchored at P_tag + (h/sz)*sun_dir → projected edge passes through P_tag."""
    cfg = OccluderConfig(patterns=["half"], edge_offset_max_r=0.0, plate_size_m=0.5)
    strategy = OccluderStrategy(cfg)
    sun_dir = sun_unit_vector(0.785398, 0.45)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    target = (0.3, -0.2, 0.0)
    # Camera looking away
    cam = _mock_cam((5.0, 5.0, 5.0))
    mat = np.array(cam.transform_matrix)
    mat[:3, 2] = -np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    cam.transform_matrix = mat.tolist()

    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[target], camera_recipes=[cam]
    )
    assert len(out) == 1

    plate = out[0]
    assert plate.rotation_euler is not None
    theta = plate.rotation_euler[2]
    e_perp = (-math.sin(theta), math.cos(theta))

    sxy = _shadow_xy(plate.location, sun_dir)
    dx = sxy[0] - target[0]
    dy = sxy[1] - target[1]
    dist_along_perp = dx * e_perp[0] + dy * e_perp[1]
    assert math.isclose(abs(dist_along_perp), cfg.plate_size_m / 2.0, abs_tol=1e-9)


def test_sliding_loop_clears_camera_view():
    """If a camera is looking at the initial plate, it must slide up until clear."""
    cfg = OccluderConfig(
        patterns=["half"],
        height_min_m=0.1,
        height_max_m=0.1,
        edge_offset_max_r=0.0
    )
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.0, elevation=math.pi / 4)
    cams = [_mock_cam((0.5, 0.0, 0.5), fov=60.0)]

    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)], camera_recipes=cams
    )

    assert out
    plate = out[0]
    assert plate.location[2] > 0.11


def test_plate_does_not_block_camera_ray_for_half_pattern():
    """For every camera, the cam→tag ray must NOT pass through the plate footprint."""
    cfg = OccluderConfig(patterns=["half"], edge_offset_max_r=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    target = (0.0, 0.0, 0.0)
    cams = [_mock_cam((0.4, 0.4, 1.0)), _mock_cam((-0.3, 0.2, 1.2))]
    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[target], camera_recipes=cams
    )
    assert out
    for plate in out:
        h = plate.location[2]
        for cam_recipe in cams:
            cam_loc = (
                cam_recipe.transform_matrix[0][3],
                cam_recipe.transform_matrix[1][3],
                cam_recipe.transform_matrix[2][3],
            )
            t = (cam_loc[2] - h) / cam_loc[2]
            rx = cam_loc[0] + t * (target[0] - cam_loc[0])
            ry = cam_loc[1] + t * (target[1] - cam_loc[1])
            assert plate.rotation_euler is not None
            theta = plate.rotation_euler[2]
            dx, dy = rx - plate.location[0], ry - plate.location[1]
            la = dx * math.cos(theta) + dy * math.sin(theta)
            lc = -dx * math.sin(theta) + dy * math.cos(theta)
            inside = (
                abs(la) <= float(plate.properties["size_along_edge_m"]) / 2
                and abs(lc) <= float(plate.properties["size_across_edge_m"]) / 2
            )
            assert not inside, f"camera ray hits plate at h={h}"


def test_plate_does_not_block_camera_ray_for_corner_pattern():
    cfg = OccluderConfig(patterns=["corner"], edge_offset_max_r=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    target = (0.0, 0.0, 0.0)
    cams = [_mock_cam((0.5, -0.2, 1.0))]
    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[target], camera_recipes=cams
    )
    assert len(out) == 1
    for plate in out:
        h = plate.location[2]
        for cam_recipe in cams:
            cam_loc = (
                cam_recipe.transform_matrix[0][3],
                cam_recipe.transform_matrix[1][3],
                cam_recipe.transform_matrix[2][3],
            )
            t = (cam_loc[2] - h) / cam_loc[2]
            rx = cam_loc[0] + t * (target[0] - cam_loc[0])
            ry = cam_loc[1] + t * (target[1] - cam_loc[1])
            assert plate.rotation_euler is not None
            theta = plate.rotation_euler[2]
            dx, dy = rx - plate.location[0], ry - plate.location[1]
            la = dx * math.cos(theta) + dy * math.sin(theta)
            lc = -dx * math.sin(theta) + dy * math.cos(theta)
            inside = (
                abs(la) <= float(plate.properties["size_along_edge_m"]) / 2
                and abs(lc) <= float(plate.properties["size_across_edge_m"]) / 2
            )
            assert not inside


def test_plate_does_not_block_camera_ray_for_multiple_tags():
    """Multi-tag scene: every (cam, tag) pair must remain unobstructed."""
    cfg = OccluderConfig(patterns=["half"], edge_offset_max_r=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    tags = [(0.0, 0.0, 0.0), (0.1, 0.05, 0.0), (-0.08, 0.07, 0.0)]
    cams = [_mock_cam((0.4, 0.4, 1.0)), _mock_cam((-0.3, 0.2, 1.2))]
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=tags, camera_recipes=cams)
    assert out
    for plate in out:
        h = plate.location[2]
        for cam_recipe in cams:
            cam_loc = (
                cam_recipe.transform_matrix[0][3],
                cam_recipe.transform_matrix[1][3],
                cam_recipe.transform_matrix[2][3],
            )
            for tag in tags:
                t = (cam_loc[2] - h) / cam_loc[2]
                rx = cam_loc[0] + t * (tag[0] - cam_loc[0])
                ry = cam_loc[1] + t * (tag[1] - cam_loc[1])
                assert plate.rotation_euler is not None
                theta = plate.rotation_euler[2]
                dx, dy = rx - plate.location[0], ry - plate.location[1]
                la = dx * math.cos(theta) + dy * math.sin(theta)
                lc = -dx * math.sin(theta) + dy * math.cos(theta)
                inside = (
                    abs(la) <= float(plate.properties["size_along_edge_m"]) / 2
                    and abs(lc) <= float(plate.properties["size_across_edge_m"]) / 2
                )
                assert not inside


def test_recipe_carries_plate_geometry_properties():
    cfg = OccluderConfig(
        patterns=["half"], plate_size_m=0.4, plate_thickness_m=0.01, albedo=0.1, roughness=0.7
    )
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.0, elevation=0.5)
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert out
    props = out[0].properties
    assert props["shape"] == "plate"
    assert props["size_along_edge_m"] == 0.4
    assert props["size_across_edge_m"] == 0.4
    assert props["thickness_m"] == 0.01
    assert props["albedo"] == 0.1
    assert props["roughness"] == 0.7


def test_determinism_same_seed_same_output():
    cfg = OccluderConfig(patterns=["half", "corner", "slit"])
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    a = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    b = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(a) == len(b)
    assert [o.location for o in a] == [o.location for o in b]
    assert [o.rotation_euler for o in a] == [o.rotation_euler for o in b]
