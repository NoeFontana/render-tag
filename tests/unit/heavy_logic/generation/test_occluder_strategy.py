"""Unit tests for OccluderStrategy: SUN-ray placement and umbra geometry."""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock

from render_tag.cli.pipeline import GenerationContext
from render_tag.core.config import DirectionalLightConfig, GenConfig
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


def test_disabled_returns_empty():
    cfg = OccluderConfig(enabled=False)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    assert strategy.sample_pose(seed=42, context=ctx, target_position=(0.0, 0.0, 0.0)) == []


def test_no_sun_returns_empty():
    cfg = OccluderConfig(enabled=True)
    strategy = OccluderStrategy(cfg)
    ctx = MagicMock(spec=GenerationContext)
    ctx.gen_config = GenConfig()
    ctx.gen_config.scene.lighting.directional = []
    ctx.output_dir = Path("output")
    assert strategy.sample_pose(seed=42, context=ctx, target_position=(0.0, 0.0, 0.0)) == []


def test_count_within_configured_range():
    cfg = OccluderConfig(count_min=2, count_max=4)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, target_position=(0.0, 0.0, 0.0))
    assert 2 <= len(out) <= 4


def test_occluders_placed_above_target_along_sun_ray():
    """Occluders must sit between the SUN and the tag (positive z, non-zero d)."""
    cfg = OccluderConfig(count_min=3, count_max=3, offset_min_m=0.02, offset_max_m=0.05)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    out = strategy.sample_pose(seed=42, context=ctx, target_position=(0.0, 0.0, 0.0))
    assert len(out) == 3
    for obj in out:
        assert obj.type == "OCCLUDER"
        # SUN ray points up and to the side; placement must have positive z.
        assert obj.location[2] > 0.0
        # Distance along the SUN ray = sqrt(x^2+y^2+z^2) ignoring lateral jitter.
        d = math.sqrt(sum(c**2 for c in obj.location))
        assert 0.01 <= d <= 0.10  # accounts for lateral_jitter_m


def test_zenith_sun_places_occluder_directly_above():
    """At elevation=pi/2, sun_dir=(0,0,1); occluders should sit at (~0, ~0, +d) from target."""
    cfg = OccluderConfig(
        count_min=1, count_max=1, offset_min_m=0.03, offset_max_m=0.03, lateral_jitter_m=0.0
    )
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.0, elevation=math.pi / 2)
    out = strategy.sample_pose(seed=42, context=ctx, target_position=(0.5, 0.5, 0.0))
    assert len(out) == 1
    x, y, z = out[0].location
    # Zenith SUN: x ≈ target_x, y ≈ target_y, z ≈ target_z + d.
    assert math.isclose(x, 0.5, abs_tol=1e-9)
    assert math.isclose(y, 0.5, abs_tol=1e-9)
    assert math.isclose(z, 0.03, abs_tol=1e-9)


def test_recipe_carries_geometry_properties():
    cfg = OccluderConfig(shape="rod", width_m=0.004, length_m=0.20, albedo=0.1, roughness=0.7)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.0, elevation=0.5)
    out = strategy.sample_pose(seed=42, context=ctx, target_position=(0.0, 0.0, 0.0))
    assert out
    props = out[0].properties
    assert props["shape"] == "rod"
    assert props["width_m"] == 0.004
    assert props["length_m"] == 0.20
    assert props["albedo"] == 0.1
    assert props["roughness"] == 0.7


def test_determinism_same_seed_same_output():
    cfg = OccluderConfig(count_min=2, count_max=4)
    strategy = OccluderStrategy(cfg)
    ctx = _ctx_with_sun(azimuth=0.785398, elevation=0.45)
    a = strategy.sample_pose(seed=42, context=ctx, target_position=(0.0, 0.0, 0.0))
    b = strategy.sample_pose(seed=42, context=ctx, target_position=(0.0, 0.0, 0.0))
    assert [o.location for o in a] == [o.location for o in b]
    assert len(a) == len(b)
