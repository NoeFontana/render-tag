"""
Shadow Renderer (2D Visualizer) for render-tag scenes.

This tool produces a fast 2D top-down visualization of a scene recipe.
It is designed to give Agents immediate feedback on layout, spacing, and overlap
without running the slow Blender rendering process.
"""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PatchCollection

from render_tag.schema import ObjectRecipe, SceneRecipe


class ShadowRenderer:
    """Renders 2D visualizations of Scene Recipes."""

    def __init__(self, recipe: SceneRecipe):
        self.recipe = recipe
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.ax.set_aspect("equal")
        self.ax.grid(True, linestyle="--", alpha=0.5)
        self.ax.set_title(f"Scene {recipe.scene_id} Layout Visualization")
        self.ax.set_xlabel("X (meters)")
        self.ax.set_ylabel("Y (meters)")

    def render(self, output_path: Path | None = None, show: bool = False):
        """Draw the scene and save/show it."""

        # 1. Draw Board/Background if present
        self._draw_board()

        # 2. Draw Tags
        self._draw_tags()

        # 3. Draw Cameras (Frustums)
        self._draw_cameras()

        # Auto-scale limits
        self.ax.autoscale_view()

        if output_path:
            plt.savefig(output_path, dpi=100)
            print(f"Visualization saved to {output_path}")

        if show:
            plt.show()

        plt.close(self.fig)

    def _draw_board(self):
        for obj in self.recipe.objects:
            if obj.type == "BOARD":
                self._draw_rect(obj, color="lightgray", alpha=0.3, label="Board")

    def _draw_tags(self):
        tag_patches = []
        for obj in self.recipe.objects:
            if obj.type == "TAG":
                rect = self._create_rect_patch(obj, color="blue", alpha=0.6)
                tag_patches.append(rect)

                # Add Tag ID text
                x, y = obj.location[0], obj.location[1]
                tag_id = obj.properties.get("tag_id", "?")
                self.ax.text(
                    x,
                    y,
                    str(tag_id),
                    color="white",
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                )

        if tag_patches:
            self.ax.add_collection(PatchCollection(tag_patches, match_original=True))

    def _draw_cameras(self):
        for i, cam in enumerate(self.recipe.cameras):
            matrix = np.array(cam.transform_matrix)
            pos = matrix[:3, 3]

            # Simple marker for camera
            self.ax.scatter(pos[0], pos[1], marker="^", c="red", s=100, label=f"Cam {i}")
            self.ax.text(pos[0], pos[1] + 0.05, f"Cam {i}", color="red", fontsize=8)

            # Draw "look vector" (Project forward vector z-axis)
            # In Blender camera looks down -Z local axis.
            # Local -Z is the 3rd column of the rotation matrix * -1
            forward = -matrix[:3, 2]  # (3rd column is Z axis)

            arrow_len = 0.5
            self.ax.arrow(
                pos[0],
                pos[1],
                forward[0] * arrow_len,
                forward[1] * arrow_len,
                head_width=0.05,
                head_length=0.1,
                fc="red",
                ec="red",
                alpha=0.5,
            )

    def _create_rect_patch(self, obj: ObjectRecipe, color, alpha=1.0) -> patches.Rectangle:
        """Create a rotated rectangle patch."""
        x, y, _ = obj.location
        # Assumes scaling is uniform or applied to XY
        # Simplification: Assume plane is mostly flat on XY or we project it
        # The scale provided is usually [1,1,1] but properties has real size

        width = 0.1
        height = 0.1

        if "tag_size" in obj.properties:
            width = height = obj.properties["tag_size"]

        # Check scale overrides
        width *= obj.scale[0]
        height *= obj.scale[1]

        # Rotation (Z-axis rotation)
        rot_z = obj.rotation_euler[2]  # Radians

        # Rectangle is defined by bottom-left corner, but our location is center.
        # We need to compute the unrotated bottom-left relative to center, then rotate it.
        # Actually, Matplotlib Rectangle accepts `angle` in degrees and `xy` as bottom-left.
        # BUT, rotating around center is trickier with simple Rectangle.
        # Best to key off center and rotation.

        # Calculate bottom-left corner before rotation
        w2 = width / 2
        h2 = height / 2

        # Rotate the corner offset (-w2, -h2) by rot_z
        # x_prime = x * cos - y * sin
        # y_prime = x * sin + y * cos
        cos_a = np.cos(rot_z)
        sin_a = np.sin(rot_z)

        dx = -w2 * cos_a - (-h2) * sin_a
        dy = -w2 * sin_a + (-h2) * cos_a

        bl_x = x + dx
        bl_y = y + dy

        return patches.Rectangle(
            (bl_x, bl_y),
            width,
            height,
            angle=np.degrees(rot_z),
            linewidth=1,
            edgecolor="black",
            facecolor=color,
            alpha=alpha,
        )

    def _draw_rect(self, obj: ObjectRecipe, color, alpha=1.0, label=None):
        patch = self._create_rect_patch(obj, color, alpha)
        self.ax.add_patch(patch)


def visualize_recipe(recipe_path: Path, output_dir: Path):
    """Load recipe and visualize it."""
    import json

    with open(recipe_path) as f:
        data = json.load(f)

    # Handle list of recipes
    if isinstance(data, list):
        for item in data:
            recipe = SceneRecipe.model_validate(item)
            renderer = ShadowRenderer(recipe)
            renderer.render(output_dir / f"viz_scene_{recipe.scene_id:04d}.png")
    else:
        recipe = SceneRecipe.model_validate(data)
        renderer = ShadowRenderer(recipe)
        renderer.render(output_dir / f"viz_scene_{recipe.scene_id:04d}.png")
