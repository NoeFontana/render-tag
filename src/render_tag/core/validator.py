"""
Pre-Flight Validator for Scene Recipes.

Performs static analysis on scene recipes to catch errors before Blender execution.
Checks:
- Schema compliance (handled by Pydantic loading)
- Asset availability (texture paths)
- Geometric integrity (basic overlap checks)
- Logical consistency (camera counts, etc.)
"""

from pathlib import Path

from render_tag.core.schema import SceneRecipe


class AssetValidator:
    """Validator for the local asset cache."""

    def __init__(self, assets_dir: Path):
        self.assets_dir = Path(assets_dir)
        self.required_subdirs = ["hdri", "textures", "tags", "models"]

    def is_hydrated(self) -> bool:
        """Check if the assets folder exists and contains the required structure."""
        if not self.assets_dir.exists():
            return False

        # Basic check: do subdirs exist?
        for sub in self.required_subdirs:
            if not (self.assets_dir / sub).exists():
                return False

        # Heuristic check: are there actually files?
        # We check if at least one common subdir has content
        has_content = False
        for sub in ["hdri", "textures", "tags"]:
            sub_path = self.assets_dir / sub
            if sub_path.exists() and any(sub_path.iterdir()):
                has_content = True
                break

        return has_content


class RecipeValidator:
    """Validator for Scene Recipes."""

    def __init__(self, recipe: SceneRecipe):
        self.recipe = recipe
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self) -> bool:
        """Run all validation checks. Returns True if valid."""
        self.errors.clear()
        self.warnings.clear()

        self._check_assets()
        self._check_geometry()
        self._check_cameras()
        self._check_visibility()

        return len(self.errors) == 0

    def _check_visibility(self):
        """
        Check if tags are visible within the camera frustum using Shadow Render logic.
        Adds warnings if cameras see no tags meeting quality criteria.

        Criteria:
        - Fully within image bounds.
        - Area >= min_pixels (1 pixel per tag bit).
        - Incidence angle <= 80 degrees.
        """
        try:
            import numpy as np

            from render_tag.core.config import get_min_pixel_area
            from render_tag.generation.projection_math import (
                calculate_incidence_angle,
                calculate_pixel_area,
                get_world_matrix,
                get_world_normal,
                project_points,
            )
            from render_tag.generation.visibility import is_facing_camera
        except ImportError:
            # Skip if numpy or projection_math are not available (unlikely in host)
            return

        tags = [obj for obj in self.recipe.objects if obj.type == "TAG"]
        if not tags:
            return

        for cam_idx, cam in enumerate(self.recipe.cameras):
            cam_matrix = np.array(cam.transform_matrix)
            cam_location = cam_matrix[:3, 3]
            res = cam.intrinsics.resolution
            fov = cam.intrinsics.fov

            valid_tags_in_view = 0

            for tag in tags:
                family = tag.properties.get("tag_family", "tag36h11")

                # Priority: CameraRecipe override -> tag bit count
                min_area = cam.min_tag_pixels or get_min_pixel_area(family)
                max_area = cam.max_tag_pixels or (res[0] * res[1])

                size = tag.properties.get("tag_size", 0.1)
                hs = size / 2.0
                # Define 4 corners of the tag in local space
                corners_local = np.array(
                    [
                        [-hs, -hs, 0],
                        [hs, -hs, 0],
                        [hs, hs, 0],
                        [-hs, hs, 0],
                    ]
                )

                # Transform corners to world space
                tag_world_mat = get_world_matrix(tag.location, tag.rotation_euler, tag.scale)
                tag_normal = get_world_normal(tag_world_mat)

                # Facing Check
                if not is_facing_camera(np.array(tag.location), tag_normal, cam_location):
                    continue

                corners_world_h = (tag_world_mat @ np.hstack([corners_local, np.ones((4, 1))]).T).T

                corners_world = corners_world_h[:, :3]

                # Project to pixel space
                pixels = project_points(corners_world, cam_matrix, res, fov)

                # 1. Check if Fully in bounds
                fully_in_bounds = True
                for x, y in pixels:
                    if not (0 <= x <= res[0] and 0 <= y <= res[1]):
                        fully_in_bounds = False
                        break

                if not fully_in_bounds:
                    continue

                # 2. Check Pixel Area
                area = calculate_pixel_area(pixels)
                if area < min_area or area > max_area:
                    continue

                # 3. Check Incidence Angle
                angle = calculate_incidence_angle(cam_matrix, tag_world_mat)
                if angle > 80.0:
                    continue

                # If we reach here, the tag is valid
                valid_tags_in_view += 1

            if valid_tags_in_view == 0:
                self.warnings.append(
                    f"Camera {cam_idx}: No tags meet visibility criteria "
                    f"(fully in view, area >= {min_area}, angle <= 80°)"
                )

    def _check_assets(self):
        """Check if referenced assets exist on disk."""
        # 1. Check World Assets
        hdri = self.recipe.world.background_hdri
        if hdri:
            path = Path(hdri)
            if not path.exists():
                self.errors.append(f"World: HDRI background not found: {path}")

        tex = self.recipe.world.texture_path
        if tex:
            path = Path(tex)
            if not path.exists():
                self.errors.append(f"World: Background texture not found: {path}")

        # 2. Check Object Assets
        for obj in self.recipe.objects:
            if obj.type == "TAG":
                # In generator we might not have set texture_path explicitly if using properties
                # But if texture_path IS set, verify it.
                if obj.texture_path:
                    path = Path(obj.texture_path)
                    if not path.exists():
                        self.errors.append(f"Object '{obj.name}': Texture path not found: {path}")

                # Check properties for implicit paths
                base_path = obj.properties.get("texture_base_path")
                if base_path:
                    # heuristic check
                    # We can't easily check exact file without re-implementing logic
                    # relying on basic existence of directory
                    path = Path(base_path)
                    if (
                        not path.exists() and not path.parent.exists()
                    ):  # Allow for relative paths from repo root logic
                        # Try resolving relative to CWD or repo root
                        # For now, just warn if it looks suspicious
                        pass

    def _check_geometry(self):
        """Check for physical intersections and board boundaries."""
        tag_boxes = []
        board_aabb = None

        # 1. Find Board Boundaries
        for obj in self.recipe.objects:
            if obj.type == "BOARD":
                props = obj.properties
                width = props.get("cols", 1) * props.get("square_size", 0.1)
                height = props.get("rows", 1) * props.get("square_size", 0.1)
                x, y = obj.location[0], obj.location[1]
                # Assuming centered at location
                board_aabb = (x - width / 2, x + width / 2, y - height / 2, y + height / 2)
                break

        # 2. Analyze Tags
        for _i, obj in enumerate(self.recipe.objects):
            if obj.type == "TAG":
                # properties has tag_size
                size = obj.properties.get("tag_size", 0.1)
                # Apply scale
                w = size * obj.scale[0]
                h = size * obj.scale[1]

                x, y = obj.location[0], obj.location[1]

                # Simple AABB (Axis Aligned Bounding Box) - ignores rotation for this quick check
                xmin, xmax = x - w / 2, x + w / 2
                ymin, ymax = y - h / 2, y + h / 2
                tag_boxes.append((obj, xmin, xmax, ymin, ymax))

                # Check if tag is within board boundaries
                if board_aabb:
                    bx_min, bx_max, by_min, by_max = board_aabb
                    # Use a small buffer (1mm) for floating point
                    if (
                        xmin < bx_min - 0.001
                        or xmax > bx_max + 0.001
                        or ymin < by_min - 0.001
                        or ymax > by_max + 0.001
                    ):
                        self.warnings.append(f"Tag '{obj.name}' is outside board boundaries.")

        # O(N^2) overlap check
        for i in range(len(tag_boxes)):
            for j in range(i + 1, len(tag_boxes)):
                obj1, xmin1, xmax1, ymin1, ymax1 = tag_boxes[i]
                obj2, xmin2, xmax2, ymin2, ymax2 = tag_boxes[j]

                # AABB Overlap check (with 1mm tolerance to avoid edge cases)
                if (
                    xmin1 < xmax2 - 0.001
                    and xmax1 > xmin2 + 0.001
                    and ymin1 < ymax2 - 0.001
                    and ymax1 > ymin2 + 0.001
                ):
                    # Check Z to ensure they aren't stacked?
                    z1, z2 = obj1.location[2], obj2.location[2]
                    if abs(z1 - z2) < 0.001:
                        self.warnings.append(f"Overlap {obj1.name}-{obj2.name}")

    def _check_cameras(self):
        """Check camera configuration."""
        if not self.recipe.cameras:
            self.errors.append("No cameras defined in scene.")

        for i, cam in enumerate(self.recipe.cameras):
            # Check intrinsics
            w, h = cam.intrinsics.resolution
            if w <= 0 or h <= 0:
                self.errors.append(f"Camera {i}: Invalid resolution {w}x{h}")


def validate_recipe_file(path: Path) -> tuple[bool, list[str], list[str]]:
    """Load and validate a recipe file."""
    import json

    with open(path) as f:
        data = json.load(f)

    all_errors = []
    all_warnings = []
    is_valid = True

    recipes_data = data if isinstance(data, list) else [data]

    for item in recipes_data:
        try:
            recipe = SceneRecipe.model_validate(item)
            validator = RecipeValidator(recipe)
            if not validator.validate():
                is_valid = False

            if validator.errors:
                all_errors.append(f"Scene {recipe.scene_id} Errors:")
                all_errors.extend([f"  - {e}" for e in validator.errors])

            if validator.warnings:
                all_warnings.append(f"Scene {recipe.scene_id} Warnings:")
                all_warnings.extend([f"  - {w}" for w in validator.warnings])

        except Exception as e:
            is_valid = False
            all_errors.append(f"Schema Validation Error: {e}")

    return is_valid, all_errors, all_warnings
