"""
Visualization tools for render-tag datasets and scene recipes.
"""

import csv
from pathlib import Path
from typing import Any

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PatchCollection
from PIL import Image, ImageDraw
from rich.console import Console

from render_tag.schema import ObjectRecipe, SceneRecipe

console = Console()


class ShadowRenderer:
    """Renders 2D visualizations of Scene Recipes (fast top-down layout)."""

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
        self._draw_board()
        self._draw_tags()
        self._draw_cameras()
        self.ax.autoscale_view()

        if output_path:
            plt.savefig(output_path, dpi=100)
            console.print(f"[dim]Visualization saved to:[/dim] {output_path.name}")

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

            self.ax.scatter(pos[0], pos[1], marker="^", c="red", s=100)
            self.ax.text(pos[0], pos[1] + 0.05, f"Cam {i}", color="red", fontsize=8)

            forward = -matrix[:3, 2]
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
        width = obj.properties.get("tag_size", 0.1)
        height = width

        width *= obj.scale[0]
        height *= obj.scale[1]

        rot_z = obj.rotation_euler[2]
        w2, h2 = width / 2, height / 2

        cos_a = np.cos(rot_z)
        sin_a = np.sin(rot_z)

        dx = -w2 * cos_a - (-h2) * sin_a
        dy = -w2 * sin_a + (-h2) * cos_a

        return patches.Rectangle(
            (x + dx, y + dy),
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


def visualize_dataset(
    output_dir: Path,
    specific_image: Any = None,
    save_viz: bool = True,
) -> None:
    """Visualize dataset detections overlaid on rendered images."""
    csv_path = output_dir / "tags.csv"
    images_dir = output_dir / "images"
    viz_dir = output_dir / "visualizations"

    if not csv_path.exists():
        console.print(f"[bold red]Error:[/bold red] CSV file not found: {csv_path}")
        return

    detections: dict[str, list[dict]] = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_id = row["image_id"]
            if img_id not in detections:
                detections[img_id] = []
            detections[img_id].append(
                {
                    "tag_id": int(row["tag_id"]),
                    "corners": [
                        (float(row["x1"]), float(row["y1"])),
                        (float(row["x2"]), float(row["y2"])),
                        (float(row["x3"]), float(row["y3"])),
                        (float(row["x4"]), float(row["y4"])),
                    ],
                }
            )

    if save_viz:
        viz_dir.mkdir(parents=True, exist_ok=True)

    image_ids = (
        [specific_image]
        if specific_image and specific_image in detections
        else list(detections.keys())
    )

    for image_id in image_ids:
        img_path = images_dir / f"{image_id}.png"
        if not img_path.exists():
            continue

        img = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        for det in detections[image_id]:
            corners = det["corners"]
            for i in range(4):
                draw.line([corners[i], corners[(i + 1) % 4]], fill="lime", width=2)
            draw.ellipse(
                [corners[0][0] - 4, corners[0][1] - 4, corners[0][0] + 4, corners[0][1] + 4],
                fill="red",
            )

        if save_viz:
            out_path = viz_dir / f"{image_id}_viz.png"
            img.save(out_path)
            console.print(f"[dim]Saved visualization:[/dim] {out_path.name}")

        if specific_image:
            img.show()


def visualize_recipe(recipe_path: Path, output_dir: Path):
    """Load recipe and visualize it in 2D."""
    import json

    with open(recipe_path) as f:
        data = json.load(f)

    recipes = data if isinstance(data, list) else [data]
    for item in recipes:
        recipe = SceneRecipe.model_validate(item)
        renderer = ShadowRenderer(recipe)
        renderer.render(output_dir / f"viz_scene_{recipe.scene_id:04d}.png")
