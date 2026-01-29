"""
Scene Generator for render-tag.

Initializes scene configurations and generates "Recipes" that can be executed
by a separate Blender process. This isolates logical calculations from Blender.
"""

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from render_tag.common.constants import TAG_GRID_SIZES
from render_tag.geometry.board import (
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
)
from render_tag.geometry.camera import sample_camera_pose, validate_camera_pose
from render_tag.geometry.math import look_at_rotation # Added for potentially more complex orientations


@dataclass
class ObjectRecipe:
    """Recipe for a single Blender object."""
    type: str  # "MESH", "PLANE", "TAG", etc.
    name: str
    location: List[float]
    rotation_euler: List[float]
    scale: List[float]
    properties: Dict[str, Any] = field(default_factory=dict)
    material: Optional[str] = None
    texture_path: Optional[str] = None


@dataclass
class CameraRecipe:
    """Recipe for a camera pose and intrinsics."""
    transform_matrix: List[List[float]]
    intrinsics: Dict[str, Any]


@dataclass
class SceneRecipe:
    """Complete recipe for a single scene."""
    scene_id: int
    objects: List[ObjectRecipe] = field(default_factory=list)
    cameras: List[CameraRecipe] = field(default_factory=list)
    world: Dict[str, Any] = field(default_factory=dict)


class Generator:
    """Generates scene recipes based on configuration."""

    def __init__(self, config: Dict[str, Any], output_dir: Path):
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self) -> List[SceneRecipe]:
        """Generate all scene recipes requested in the config."""
        num_scenes = self.config.get("dataset", {}).get("num_scenes", 1)
        recipes = []
        for i in range(num_scenes):
            recipes.append(self.generate_scene(i))
        return recipes

    def generate_scene(self, scene_id: int) -> SceneRecipe:
        """Generate a single scene recipe."""
        recipe = SceneRecipe(scene_id=scene_id)
        
        # 1. Setup World/Environment
        recipe.world = self._generate_world_config()

        # 2. Setup Tags and Layout
        recipe.objects = self._generate_layout_objects(scene_id)

        # 3. Setup Cameras
        recipe.cameras = self._generate_camera_recipes()

        return recipe

    def _generate_world_config(self) -> Dict[str, Any]:
        scene_config = self.config.get("scene", {})
        lighting_config = scene_config.get("lighting", {})
        
        return {
            "background_hdri": scene_config.get("background_hdri"),
            "lighting": {
                "intensity": random.uniform(
                    lighting_config.get("intensity_min", 50),
                    lighting_config.get("intensity_max", 500)
                )
            }
        }

    def _generate_layout_objects(self, scene_id: int) -> List[ObjectRecipe]:
        tag_config = self.config.get("tag", {})
        scenario_config = self.config.get("scenario", {})
        scene_config = self.config.get("scene", {})
        
        is_flying = scenario_config.get("flying", False)
        layout_list = scene_config.get("layouts") or scenario_config.get("layouts") or ["plain"]
        layout_mode = layout_list[scene_id % len(layout_list)]

        objects = []
        
        # Calculate grid size
        grid_size = tag_config.get("grid_size", scenario_config.get("grid_size", [6, 6]))
        cols, rows = grid_size[0], grid_size[1]
        
        tag_size = tag_config.get("size_meters", 0.1)
        tag_families = scenario_config.get("tag_families", ["tag36h11"])
        if "family" in tag_config:
            tag_families = [tag_config["family"]]

        # Simplified Logic for tag count and placement
        # (Mirroring compositor.py logic)
        if layout_mode == "cb":
            num_tags = (cols * rows + 1) // 2
        elif layout_mode == "aprilgrid":
            num_tags = cols * rows
        else:
            tags_range = tag_config.get("tags_per_scene", scenario_config.get("tags_per_scene", [1, 5]))
            num_tags = random.randint(tags_range[0], tags_range[1])

        # Generate Tag Objects (Abstractly)
        for i in range(num_tags):
            family = random.choice(tag_families)
            # We don't know the exact texture path yet if it depends on Blender's library,
            # but we can pass instructions.
            texture_base_path = tag_config.get("texture_path")
            
            tag_obj = ObjectRecipe(
                type="TAG",
                name=f"Tag_{i}",
                location=[0, 0, 0],
                rotation_euler=[0, 0, 0],
                scale=[1, 1, 1],
                properties={
                    "tag_id": i,
                    "tag_family": family,
                    "tag_size": tag_size,
                    "texture_base_path": texture_base_path
                }
            )
            objects.append(tag_obj)

        # Apply Layout (Math only)
        if is_flying:
            self._apply_flying_layout(objects, tag_config.get("scatter_radius", 0.5))
        else:
            # Layout math...
            self._apply_grid_layout(objects, layout_mode, cols, rows, tag_size)
            
            # Add static objects like board
            if layout_mode in ("cb", "aprilgrid", "plain"):
                # Use square_size logic consistent with _apply_grid_layout
                tag_families = scenario_config.get("tag_families", ["tag36h11"])
                primary_family = tag_families[0]
                from render_tag.common.constants import TAG_GRID_SIZES
                tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)
                
                tag_spacing_bits = scenario_config.get("tag_spacing_bits", 
                                                     tag_config.get("tag_spacing_bits", 2))
                tag_spacing = (tag_spacing_bits / tag_bit_grid_size) * tag_size
                square_size = tag_size + tag_spacing

                objects.append(ObjectRecipe(
                    type="BOARD",
                    name="Board_Background",
                    location=[0, 0, -0.005],
                    rotation_euler=[0, 0, 0],
                    scale=[1, 1, 1],
                    properties={
                        "mode": layout_mode, 
                        "cols": cols, 
                        "rows": rows, 
                        "tag_size": tag_size,
                        "square_size": square_size
                    }
                ))

        return objects

    def _apply_flying_layout(self, objects: List[ObjectRecipe], radius: float):
        for obj in objects:
            obj.location = [
                random.uniform(-radius, radius),
                random.uniform(-radius, radius),
                random.uniform(0.1, radius * 2)
            ]
            obj.rotation_euler = [
                random.uniform(0, 2 * np.pi),
                random.uniform(0, 2 * np.pi),
                random.uniform(0, 2 * np.pi)
            ]

    def _apply_grid_layout(self, objects: List[ObjectRecipe], mode: str, cols: int, rows: int, tag_size: float):
        """Apply grid layout (math only)."""
        scenario_config = self.config.get("scenario", {})
        tag_config = self.config.get("tag", {})

        # Spacing logic
        tag_families = scenario_config.get("tag_families", ["tag36h11"])
        primary_family = tag_families[0]
        from render_tag.common.constants import TAG_GRID_SIZES
        tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)
        
        tag_spacing_bits = scenario_config.get("tag_spacing_bits", 
                                             tag_config.get("tag_spacing_bits", 2))
        tag_spacing = (tag_spacing_bits / tag_bit_grid_size) * tag_size
        square_size = tag_size + tag_spacing
        marker_margin = tag_spacing / 2.0
        corner_size = tag_spacing

        if mode == "plain":
            n = len(objects)
            if n == 0: return
            cell_size = tag_size + tag_spacing
            grid_cols = cols or int(np.ceil(np.sqrt(n)))
            grid_rows = rows or int(np.ceil(n / grid_cols))
            
            grid_width = (grid_cols - 1) * cell_size
            grid_height = (grid_rows - 1) * cell_size
            start_x = -grid_width / 2
            start_y = -grid_height / 2

            for i, obj in enumerate(objects):
                col, row = i % grid_cols, i // grid_cols
                obj.location = [start_x + col * cell_size, start_y + row * cell_size, 0.002]
        
        elif mode == "cb":
            spec = BoardSpec(rows=rows, cols=cols, square_size=square_size, marker_margin=marker_margin, board_type=BoardType.CHARUCO)
            layout = compute_charuco_layout(spec, center=(0, 0, 0))
            self._apply_layout_to_objects(objects, layout, spec.marker_size)
            
        elif mode == "aprilgrid":
            spec = BoardSpec(rows=rows, cols=cols, square_size=square_size, marker_margin=marker_margin, board_type=BoardType.APRILGRID)
            layout = compute_aprilgrid_layout(spec, corner_size=corner_size, center=(0, 0, 0))
            self._apply_layout_to_objects(objects, layout, spec.marker_size)

    def _apply_layout_to_objects(self, objects: List[ObjectRecipe], layout: Any, marker_size: float):
        tag_idx = 0
        for sq in layout.squares:
            if sq.has_tag and tag_idx < len(objects):
                obj = objects[tag_idx]
                obj.location = [sq.center.x, sq.center.y, 0.002]
                # In the recipe, we store the target size/scale
                # The executor will handle the actual Blender scaling
                obj.properties["marker_size"] = marker_size
                tag_idx += 1

    def _generate_camera_recipes(self) -> List[CameraRecipe]:
        camera_config = self.config.get("camera", {})
        samples_per_scene = camera_config.get("samples_per_scene", 10)
        
        recipes = []
        for i in range(samples_per_scene):
            # Sample pose
            # For now, simple look-at-origin
            pose = sample_camera_pose(
                look_at_point=[0, 0, 0],
                min_distance=camera_config.get("min_distance", 0.5),
                max_distance=camera_config.get("max_distance", 2.0),
            )
            
            recipes.append(CameraRecipe(
                transform_matrix=pose.transform_matrix.tolist(),
                intrinsics=self._get_intrinsics_config()
            ))
        return recipes

    def _get_intrinsics_config(self) -> Dict[str, Any]:
        camera_config = self.config.get("camera", {})
        return {
            "resolution": camera_config.get("resolution", [640, 480]),
            "fov": camera_config.get("fov", 60.0),
            "intrinsics": camera_config.get("intrinsics", {})
        }

    def save_recipe_json(self, recipes: List[SceneRecipe], filename: str = "scene_recipes.json"):
        path = self.output_dir / filename
        data = [self._serialize_recipe(r) for r in recipes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def _serialize_recipe(self, recipe: SceneRecipe) -> Dict[str, Any]:
        import dataclasses
        return dataclasses.asdict(recipe)
