"""
Schema for render-tag Scene Recipes.

This module defines strict contracts for scene data generation using Pydantic.
This ensures that the "Generator" (Python logic) produces valid, typed data
that the "Executor" (Blender) or "Shadow Renderer" (Visualization) can consume safely.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ObjectRecipe(BaseModel):
    """Recipe for a single object in the scene."""

    type: str = Field(description="Object type: TAG, BOARD, PLANE, etc.")
    name: str = Field(description="Unique name for the object")
    location: list[float] = Field(
        min_length=3, max_length=3, description="[x, y, z] location in meters"
    )
    rotation_euler: list[float] = Field(
        min_length=3, max_length=3, description="[x, y, z] euler rotation in radians"
    )
    scale: list[float] = Field(default=[1.0, 1.0, 1.0], min_length=3, max_length=3)
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Custom properties: tag_id, family, etc."
    )
    material: str | None = None
    texture_path: str | None = None


class CameraIntrinsics(BaseModel):
    """Camera intrinsic parameters."""

    resolution: list[int] = Field(
        min_length=2, max_length=2, description="[width, height] in pixels"
    )
    fov: float = Field(default=60.0, description="Horizontal field of view in degrees")
    intrinsics: dict[str, Any] = Field(
        default_factory=dict, description="Explicit K matrix or focal lengths"
    )


class CameraRecipe(BaseModel):
    """Recipe for a camera pose and configuration."""

    transform_matrix: list[list[float]] = Field(
        description="4x4 Camera-to-World transformation matrix"
    )
    intrinsics: CameraIntrinsics

    # Phase 5: Sensor Simulation
    velocity: list[float] | None = Field(
        default=None, description="[vx, vy, vz] velocity vector in m/s"
    )
    shutter_time_ms: float | None = Field(default=None, description="Shutter time in ms")
    fstop: float | None = Field(default=None, description="Aperture f-stop")
    focus_distance: float | None = Field(default=None, description="Focus distance in meters")
    iso_noise: float | None = Field(default=None, description="ISO noise level (0-1)")


class LightingConfig(BaseModel):
    """Lighting configuration for the scene."""

    intensity: float = Field(default=100.0, description="Light intensity/strength")
    color: list[float] = Field(default=[1.0, 1.0, 1.0], min_length=3, max_length=3)


class WorldRecipe(BaseModel):
    """World environment configuration."""

    background_hdri: str | None = Field(default=None, description="Path to HDRI file")
    lighting: LightingConfig = Field(default_factory=LightingConfig)
    use_nodes: bool = True


class SceneRecipe(BaseModel):
    """Complete recipe for a single generated scene."""

    model_config = ConfigDict(extra="forbid")

    scene_id: int = Field(description="Unique ID for this scene")
    world: WorldRecipe = Field(default_factory=WorldRecipe)
    objects: list[ObjectRecipe] = Field(default_factory=list)
    cameras: list[CameraRecipe] = Field(default_factory=list)
