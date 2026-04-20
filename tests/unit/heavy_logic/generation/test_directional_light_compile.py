"""Compiler-side tests for the directional (SUN) light overlay.

Verifies that ``DirectionalLightConfig`` is plumbed from ``LightingConfig``
through the world-recipe builder into a ``LightRecipe(type='SUN', ...)`` with
a location/rotation pair that orients Blender's SUN toward the origin.
"""

from __future__ import annotations

import math

import pytest

from render_tag.core.config import DirectionalLightConfig, GenConfig
from render_tag.generation.compiler import SUN_DISTANCE, SceneCompiler


def _compile(config: GenConfig):
    compiler = SceneCompiler(config, global_seed=42)
    return compiler.compile_scene(0)


def test_directional_none_preserves_three_point_lights():
    """Default behavior: three hemispheric POINT lights, byte-identical to pre-Phase-3."""
    config = GenConfig()
    recipe = _compile(config)

    assert len(recipe.world.lights) == 3
    for light in recipe.world.lights:
        assert light.type == "POINT"
        assert light.rotation_euler is None


def test_directional_single_emits_sun_after_points():
    """A single DirectionalLightConfig appends one SUN light at the end."""
    config = GenConfig()
    config.scene.lighting.directional = [
        DirectionalLightConfig(azimuth=0.0, elevation=0.0, intensity=5.0)
    ]
    recipe = _compile(config)

    assert len(recipe.world.lights) == 4
    sun = recipe.world.lights[-1]
    assert sun.type == "SUN"
    assert sun.intensity == 5.0
    assert sun.radius == 0.0
    assert sun.rotation_euler is not None


def test_directional_list_emits_one_sun_per_entry():
    """A list directional config emits one SUN per entry."""
    config = GenConfig()
    config.scene.lighting.directional = [
        DirectionalLightConfig(azimuth=0.0, elevation=0.3, intensity=3.0, color=[1.0, 0.7, 0.4]),
        DirectionalLightConfig(
            azimuth=math.pi, elevation=0.3, intensity=3.0, color=[0.8, 0.9, 1.0]
        ),
    ]
    recipe = _compile(config)

    suns = [light for light in recipe.world.lights if light.type == "SUN"]
    assert len(suns) == 2
    assert suns[0].color == [1.0, 0.7, 0.4]
    assert suns[1].color == [0.8, 0.9, 1.0]


@pytest.mark.parametrize(
    "azimuth,elevation,expected_location",
    [
        (0.0, 0.0, [SUN_DISTANCE, 0.0, 0.0]),
        (math.pi / 2, 0.0, [0.0, SUN_DISTANCE, 0.0]),
        (0.0, math.pi / 2, [0.0, 0.0, SUN_DISTANCE]),
    ],
)
def test_sun_location_encodes_azimuth_elevation(
    azimuth: float, elevation: float, expected_location: list[float]
) -> None:
    """Sun location sits at ``SUN_DISTANCE`` on the unit-direction vector."""
    config = GenConfig()
    config.scene.lighting.directional = [
        DirectionalLightConfig(azimuth=azimuth, elevation=elevation, intensity=5.0)
    ]
    recipe = _compile(config)

    sun = recipe.world.lights[-1]
    for actual, expected in zip(sun.location, expected_location, strict=True):
        assert math.isclose(actual, expected, abs_tol=1e-9)


def test_sun_rotation_points_light_at_origin():
    """rotation_euler should map Blender's default -Z to the origin-ward direction."""
    config = GenConfig()
    config.scene.lighting.directional = [
        DirectionalLightConfig(azimuth=math.pi / 4, elevation=0.3, intensity=5.0)
    ]
    recipe = _compile(config)

    sun = recipe.world.lights[-1]
    assert sun.rotation_euler is not None
    rx, ry, rz = sun.rotation_euler

    # Verify the rotation maps (0, 0, -1) to the direction from the sun toward origin.
    # Direction from sun at location L toward origin: -L / |L|.
    loc = sun.location
    norm = math.sqrt(sum(c * c for c in loc))
    expected_dir = [-c / norm for c in loc]

    # Apply Rz · Rx to (0, 0, -1): XYZ-Euler with ry=0 gives
    # Rx(rx)·(0,0,-1) = (0, sin(rx), -cos(rx))
    # Rz(rz)·(0, sin(rx), -cos(rx)) = (-sin(rz)sin(rx), cos(rz)sin(rx), -cos(rx))
    actual_dir = [
        -math.sin(rz) * math.sin(rx),
        math.cos(rz) * math.sin(rx),
        -math.cos(rx),
    ]
    for a, e in zip(actual_dir, expected_dir, strict=True):
        assert math.isclose(a, e, abs_tol=1e-9), f"ry={ry}: {actual_dir} vs {expected_dir}"
