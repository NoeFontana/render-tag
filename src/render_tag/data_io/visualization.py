"""
Visualization tools for render-tag datasets and scene recipes.
"""

import csv
from pathlib import Path
from typing import Any

try:
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt
    from matplotlib.collections import PatchCollection
except ImportError:
    patches = None
    plt = None
    PatchCollection = None

import numpy as np
from PIL import Image, ImageDraw
from rich.console import Console

from render_tag.core.schema import ObjectRecipe, SceneRecipe

console = Console()


class ShadowRenderer:
    """Renders 2D visualizations of Scene Recipes (fast top-down layout)."""

    def __init__(self, recipe: SceneRecipe):
        if plt is None:
            raise ImportError("matplotlib is not installed. Install with 'pip install matplotlib'.")

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

            info = f"Cam {i}"
            if cam.iso_noise and cam.iso_noise > 0:
                info += f"\nISO: {cam.iso_noise}"
            if cam.sensor_noise:
                info += f"\nNoise: {cam.sensor_noise.model.value}"

            self.ax.text(pos[0], pos[1] + 0.05, info, color="red", fontsize=8)

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

        # Staff Engineer: Handle None for rotation_euler (default to zero rotation)
        rotation = obj.rotation_euler or [0.0, 0.0, 0.0]
        rot_z = rotation[2]
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
    csv_path = output_dir / "ground_truth.csv"
    coco_path = output_dir / "coco_labels.json"
    images_dir = output_dir / "images"
    viz_dir = output_dir / "visualizations"

    detections: dict[str, list[dict]] = {}

    if coco_path.exists():
        detections = _load_detections_from_coco(coco_path)
    elif csv_path.exists():
        detections = _load_detections_from_csv(csv_path)
    else:
        # Fallback to legacy names
        legacy_csv = output_dir / "tags.csv"
        legacy_coco = output_dir / "annotations.json"
        if legacy_coco.exists():
            detections = _load_detections_from_coco(legacy_coco)
        elif legacy_csv.exists():
            detections = _load_detections_from_csv(legacy_csv)
        else:
            msg = f"No annotations found (ground_truth.csv or coco_labels.json) in {output_dir}"
            console.print(f"[bold red]Error:[/bold red] {msg}")
            return

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
        _draw_overlay_on_image(img, detections[image_id])

        if save_viz:
            out_path = viz_dir / f"{image_id}_viz.png"
            img.save(out_path)
            console.print(f"[dim]Saved visualization:[/dim] {out_path.name}")

        if specific_image:
            img.show()


def _load_detections_from_coco(coco_path: Path) -> dict[str, list[dict]]:
    """Load and format detections from COCO JSON."""
    import json

    detections = {}
    with open(coco_path) as f:
        coco = json.load(f)

    # Map image id to file name
    img_map = {img["id"]: Path(img["file_name"]).stem for img in coco["images"]}

    for ann in coco["annotations"]:
        img_id_str = img_map.get(ann["image_id"])
        if not img_id_str:
            continue

        if img_id_str not in detections:
            detections[img_id_str] = []

        # Extract corners from keypoints [x, y, v, x, y, v...]
        kp = ann.get("keypoints", [])
        corners = []
        if kp:
            for i in range(0, len(kp), 3):
                corners.append((float(kp[i]), float(kp[i + 1])))
        else:
            # Fallback to bbox if no keypoints (approximation)
            x, y, w, h = ann["bbox"]
            corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]

        detections[img_id_str].append(
            {"tag_id": ann.get("attributes", {}).get("tag_id", "?"), "corners": corners}
        )
    return detections


def _load_detections_from_csv(csv_path: Path) -> dict[str, list[dict]]:
    """Load and format detections from legacy CSV."""
    detections = {}
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
    return detections


def _draw_overlay_on_image(img: Image.Image, detections: list[dict]):
    """Draw lime edges, red crosshairs, corner indices and winding arrows."""
    from PIL import ImageFont

    draw = ImageDraw.Draw(img)

    # Try to load a font, fallback to default
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for det in detections:
        corners = det["corners"]
        # Draw edges and winding arrows
        if len(corners) == 4:
            for i in range(4):
                p1 = corners[i]
                p2 = corners[(i + 1) % 4]
                # Edge
                draw.line([p1, p2], fill="lime", width=2)

                # Winding arrow (cyan) at midpoint
                mid_x = (p1[0] + p2[0]) / 2
                mid_y = (p1[1] + p2[1]) / 2
                # Small directional tick
                v_x = p2[0] - p1[0]
                v_y = p2[1] - p1[1]
                v_len = (v_x**2 + v_y**2) ** 0.5
                if v_len > 1e-6:
                    v_x /= v_len
                    v_y /= v_len
                    # Arrow head
                    ah_len = 5
                    ah_angle = 0.5  # radians
                    # Back vectors
                    b1_x = -v_x * np.cos(ah_angle) + v_y * np.sin(ah_angle)
                    b1_y = -v_x * np.sin(ah_angle) - v_y * np.cos(ah_angle)
                    b2_x = -v_x * np.cos(ah_angle) - v_y * np.sin(ah_angle)
                    b2_y = v_x * np.sin(ah_angle) - v_y * np.cos(ah_angle)

                    draw.line(
                        [(mid_x, mid_y), (mid_x + b1_x * ah_len, mid_y + b1_y * ah_len)],
                        fill="cyan",
                        width=2,
                    )
                    draw.line(
                        [(mid_x, mid_y), (mid_x + b2_x * ah_len, mid_y + b2_y * ah_len)],
                        fill="cyan",
                        width=2,
                    )

        # Draw corners (crosshairs for precision) and indices
        for i, corner in enumerate(corners):
            cx, cy = corner
            r = 3
            # Crosshair
            draw.line([(cx - r, cy), (cx + r, cy)], fill="red", width=1)
            draw.line([(cx, cy - r), (cx, cy + r)], fill="red", width=1)

            # Index (yellow)
            if font:
                draw.text((cx + 5, cy + 5), str(i), fill="yellow", font=font)
            else:
                draw.text((cx + 5, cy + 5), str(i), fill="yellow")


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
