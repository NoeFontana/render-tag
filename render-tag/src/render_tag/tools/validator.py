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

from render_tag.schema import SceneRecipe


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

        return len(self.errors) == 0

    def _check_assets(self):
        """Check if referenced assets exist on disk."""
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
        """Check for physical intersectons."""
        # Simple bounding box check for tags (assuming flat on Z=0 for grid layouts)
        # This is strictly 2D XY check

        tag_boxes = []

        for i, obj in enumerate(self.recipe.objects):
            if obj.type == "TAG":
                # properties has tag_size
                size = obj.properties.get("tag_size", 0.1)
                # Apply scale
                w = size * obj.scale[0]
                h = size * obj.scale[1]

                x, y = obj.location[0], obj.location[1]

                # Simple AABB (Axis Aligned Bounding Box) - ignores rotation for this quick check
                # This could be a source of false positives for rotated tags, so maybe just warn?
                # Or implemented OBB overlap.

                # Let's do a simple distance check. Max radius is sqrt(w^2 + h^2)/2
                radius = (w**2 + h**2) ** 0.5 / 2.0
                tag_boxes.append((i, obj, x, y, radius))

        # O(N^2) check
        for i in range(len(tag_boxes)):
            for j in range(i + 1, len(tag_boxes)):
                _idx1, obj1, x1, y1, r1 = tag_boxes[i]
                _idx2, obj2, x2, y2, r2 = tag_boxes[j]

                dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
                min_dist = r1 + r2

                # Allow a tiny bit of overlap (floating point)
                if dist < min_dist * 0.9:  # 10% overlap tolerance
                    # Check Z to ensure they aren't stacked?
                    # Assuming planar tags on same Z
                    z1, z2 = obj1.location[2], obj2.location[2]
                    if abs(z1 - z2) < 0.001:
                        self.warnings.append(
                            f"Overlap {obj1.name}-{obj2.name} (d={dist:.3f}, req={min_dist:.3f})"
                        )

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
