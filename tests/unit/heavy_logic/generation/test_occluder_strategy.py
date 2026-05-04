"""Unit tests for OccluderStrategy: half-plane plate placement and shadow geometry."""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from render_tag.cli.pipeline import GenerationContext
from render_tag.core.config import DirectionalLightConfig, GenConfig
from render_tag.core.geometry.math import sun_unit_vector
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


def test_edge_pattern_emits_single_plate():
    cfg = OccluderConfig(patterns=["edge"], edge_offset_max_m=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(out) == 1
    assert out[0].type == "OCCLUDER"
    assert out[0].properties["shape"] == "plate"


def test_corner_pattern_emits_two_perpendicular_plates():
    cfg = OccluderConfig(patterns=["corner"], edge_offset_max_m=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(out) == 2
    theta_a = out[0].rotation_euler[2]
    theta_b = out[1].rotation_euler[2]
    diff = (theta_b - theta_a) % (2 * math.pi)
    assert math.isclose(diff, math.pi / 2, abs_tol=1e-9)


def test_slit_pattern_emits_two_parallel_plates():
    cfg = OccluderConfig(patterns=["slit"], edge_offset_max_m=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(out) == 2
    assert math.isclose(out[0].rotation_euler[2], out[1].rotation_euler[2], abs_tol=1e-9)


from render_tag.core.schema.recipe import CameraRecipe, CameraIntrinsics, ObjectRecipe

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
    k = [[f, 0, res[0]/2.0], [0, f, res[1]/2.0], [0, 0, 1]]
    
    return CameraRecipe(
        transform_matrix=mat.tolist(),
        intrinsics=CameraIntrinsics(
            resolution=list(res),
            k_matrix=k,
            fov=fov
        )
    )

def test_shadow_edge_passes_through_target_for_edge_pattern():
    """Plate edge anchored at P_tag + (h/sz)*sun_dir → projected edge passes through P_tag."""
    cfg = OccluderConfig(patterns=["edge"], edge_offset_max_m=0.0, plate_size_m=0.5)
    strategy = OccluderStrategy(cfg)
    sun_dir = sun_unit_vector(0.785398, 0.45)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    target = (0.3, -0.2, 0.0)
    # Camera looking away from the origin to ensure occluder is not visible
    cam = _mock_cam((5.0, 5.0, 5.0))
    # Rotate camera to look at (10, 10, 10) instead of origin
    mat = np.array(cam.transform_matrix)
    forward = np.array([1.0, 1.0, 1.0])
    forward /= np.linalg.norm(forward)
    # Standard Blender camera: -Z is forward, Y is up
    mat[:3, 2] = -forward 
    cam.transform_matrix = mat.tolist()
    
    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[target], camera_recipes=[cam]
    )
    assert len(out) == 1

    plate = out[0]
    theta = plate.rotation_euler[2]
    e_perp = (-math.sin(theta), math.cos(theta))

    sxy = _shadow_xy(plate.location, sun_dir)
    dx = sxy[0] - target[0]
    dy = sxy[1] - target[1]
    dist_along_perp = dx * e_perp[0] + dy * e_perp[1]
    # Shadow edge should pass through target
    assert math.isclose(abs(dist_along_perp), cfg.plate_size_m / 2.0, abs_tol=1e-9)

def test_sliding_loop_clears_camera_view():
    """If a camera is looking at the initial plate, it must slide up until clear."""
    cfg = OccluderConfig(
        patterns=["edge"], 
        height_min_m=0.1, 
        height_max_m=0.1, 
        edge_offset_max_m=0.0
    )
    strategy = OccluderStrategy(cfg)
    # Sun from +X (azimuth=0), elevation=45 deg
    ctx = _ctx_with_sun(azimuth=0.0, elevation=math.pi/4)
    sun_dir = sun_unit_vector(0.0, math.pi/4) # (0.707, 0, 0.707)
    
    # Camera positioned exactly where it will see the initial plate (h=0.1)
    # Target at origin.
    cams = [_mock_cam((0.5, 0.0, 0.5), fov=60.0)]
    
    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)], camera_recipes=cams
    )
    
    assert out
    plate = out[0]
    # It must have slid up from the initial 0.1m
    assert plate.location[2] > 0.11 
    
    # Verify shadow still passes through origin
    # Projection to Z=0: P_shadow = P_plate - (h/sz)*sun_dir
    h = plate.location[2]
    sx, sy, sz = sun_dir
    shadow_x = plate.location[0] - (h * sx / sz)
    shadow_y = plate.location[1] - (h * sy / sz)
    
    # Orientation: sun is from +X, so e_perp is (0, 1)
    # Plate theta should be 0 or pi (arc fitting angles=pi/2 for this cam)
    theta = plate.rotation_euler[2]
    e_perp = (-math.sin(theta), math.cos(theta))
    
    dx = shadow_x - 0.0
    dy = shadow_y - 0.0
    dist_along_perp = dx * e_perp[0] + dy * e_perp[1]
    assert math.isclose(abs(dist_along_perp), cfg.plate_size_m / 2.0, abs_tol=1e-9)

def test_plate_does_not_block_camera_ray_for_edge_pattern():
    """For every camera, the cam→tag ray must NOT pass through the plate footprint."""
    cfg = OccluderConfig(patterns=["edge"], edge_offset_max_m=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    target = (0.0, 0.0, 0.0)
    cams = [_mock_cam((0.4, 0.4, 1.0)), _mock_cam((-0.3, 0.2, 1.2))]
    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[target], camera_recipes=cams
    )
    assert out
    # Verify with the ray logic manually.
    for plate in out:
        h = plate.location[2]
        for cam_recipe in cams:
            cam_loc = cam_recipe.transform_matrix[0][3], cam_recipe.transform_matrix[1][3], cam_recipe.transform_matrix[2][3]
            t = (cam_loc[2] - h) / cam_loc[2]
            rx = cam_loc[0] + t * (target[0] - cam_loc[0])
            ry = cam_loc[1] + t * (target[1] - cam_loc[1])
            theta = plate.rotation_euler[2]
            dx, dy = rx - plate.location[0], ry - plate.location[1]
            la = dx * math.cos(theta) + dy * math.sin(theta)
            lc = -dx * math.sin(theta) + dy * math.cos(theta)
            inside = abs(la) <= cfg.plate_size_m / 2 and abs(lc) <= cfg.plate_size_m / 2
            assert not inside, f"camera ray hits plate at h={h}"


def test_plate_does_not_block_camera_ray_for_corner_pattern():
    cfg = OccluderConfig(patterns=["corner"], edge_offset_max_m=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    target = (0.0, 0.0, 0.0)
    cams = [_mock_cam((0.5, -0.2, 1.0))]
    out = strategy.sample_pose(
        seed=42, context=ctx, tag_positions=[target], camera_recipes=cams
    )
    assert len(out) == 2
    for plate in out:
        h = plate.location[2]
        for cam_recipe in cams:
            cam = cam_recipe.transform_matrix[0][3], cam_recipe.transform_matrix[1][3], cam_recipe.transform_matrix[2][3]
            t = (cam[2] - h) / cam[2]
            rx = cam[0] + t * (target[0] - cam[0])
            ry = cam[1] + t * (target[1] - cam[1])
            theta = plate.rotation_euler[2]
            dx, dy = rx - plate.location[0], ry - plate.location[1]
            la = dx * math.cos(theta) + dy * math.sin(theta)
            lc = -dx * math.sin(theta) + dy * math.cos(theta)
            inside = abs(la) <= cfg.plate_size_m / 2 and abs(lc) <= cfg.plate_size_m / 2
            assert not inside


def test_plate_does_not_block_camera_ray_for_multiple_tags():
    """Multi-tag scene: every (cam, tag) pair must remain unobstructed."""
    cfg = OccluderConfig(patterns=["edge"], edge_offset_max_m=0.0)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    tags = [(0.0, 0.0, 0.0), (0.1, 0.05, 0.0), (-0.08, 0.07, 0.0)]
    cams = [_mock_cam((0.4, 0.4, 1.0)), _mock_cam((-0.3, 0.2, 1.2))]
    out = strategy.sample_pose(seed=42, context=ctx, tag_positions=tags, camera_recipes=cams)
    assert out
    for plate in out:
        h = plate.location[2]
        for cam_recipe in cams:
            cam = cam_recipe.transform_matrix[0][3], cam_recipe.transform_matrix[1][3], cam_recipe.transform_matrix[2][3]
            for tag in tags:
                t = (cam[2] - h) / cam[2]
                rx = cam[0] + t * (tag[0] - cam[0])
                ry = cam[1] + t * (tag[1] - cam[1])
                theta = plate.rotation_euler[2]
                dx, dy = rx - plate.location[0], ry - plate.location[1]
                la = dx * math.cos(theta) + dy * math.sin(theta)
                lc = -dx * math.sin(theta) + dy * math.cos(theta)
                inside = abs(la) <= cfg.plate_size_m / 2 and abs(lc) <= cfg.plate_size_m / 2
                assert not inside, (
                    f"plate at h={h} blocks ray cam={cam}→tag={tag}"
                )


def test_recipe_carries_plate_geometry_properties():
    cfg = OccluderConfig(
        patterns=["edge"], plate_size_m=0.4, plate_thickness_m=0.01, albedo=0.1, roughness=0.7
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
    cfg = OccluderConfig(patterns=["edge", "corner", "slit"])
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    a = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    b = strategy.sample_pose(seed=42, context=ctx, tag_positions=[(0.0, 0.0, 0.0)])
    assert len(a) == len(b)
    assert [o.location for o in a] == [o.location for o in b]
    assert [o.rotation_euler for o in a] == [o.rotation_euler for o in b]
