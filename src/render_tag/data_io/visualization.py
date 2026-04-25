"""
Visualization tools for render-tag datasets and scene recipes.
"""

import csv
import json
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
from render_tag.core.schema.base import KeypointVisibility

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
        self._draw_occluders()
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

    def _draw_occluders(self):
        for obj in self.recipe.objects:
            if obj.type != "OCCLUDER":
                continue
            patch = self._create_rect_patch(
                obj,
                color="#444444",
                alpha=0.85,
                width=obj.properties.get("width_m", 0.003),
                height=obj.properties.get("length_m", 0.15),
            )
            self.ax.add_patch(patch)

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

    def _create_rect_patch(
        self,
        obj: ObjectRecipe,
        color,
        alpha: float = 1.0,
        width: float | None = None,
        height: float | None = None,
    ) -> patches.Rectangle:
        """Rotated rectangle anchored at matplotlib's lower-left corner convention.

        ``width``/``height`` override the default tag_size square so
        non-square recipes (e.g. occluder rods) can reuse this helper.
        """
        x, y, _ = obj.location
        if width is None:
            width = obj.properties.get("tag_size", 0.1) * obj.scale[0]
        if height is None:
            tag_size = obj.properties.get("tag_size", 0.1)
            height = tag_size * obj.scale[1]

        rot_z = (obj.rotation_euler or [0.0, 0.0, 0.0])[2]
        cos_a, sin_a = np.cos(rot_z), np.sin(rot_z)
        w2, h2 = width / 2, height / 2

        dx = -w2 * cos_a + h2 * sin_a
        dy = -w2 * sin_a - h2 * cos_a

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

    eval_margin_px = 0
    try:
        with open(output_dir / "rich_truth.json") as f:
            rt = json.load(f)
        eval_margin_px = int(rt.get("evaluation_context", {}).get("photometric_margin_px", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass

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
        _draw_overlay_on_image(img, detections[image_id], eval_margin_px=eval_margin_px)

        if save_viz:
            out_path = viz_dir / f"{image_id}_viz.png"
            img.save(out_path)
            console.print(f"[dim]Saved visualization:[/dim] {out_path.name}")

        if specific_image:
            img.show()


def _load_detections_from_coco(coco_path: Path) -> dict[str, list[dict]]:
    """Load and format detections from COCO JSON."""
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

        kp = ann.get("keypoints", [])
        corners = []
        if kp:
            for i in range(0, min(12, len(kp)), 3):  # 12 = 4 corners x 3 fields
                v = int(kp[i + 2]) if i + 2 < len(kp) else KeypointVisibility.VISIBLE
                corners.append((float(kp[i]), float(kp[i + 1]), v))
        else:
            x, y, w, h = ann["bbox"]
            corners = [
                (x, y, KeypointVisibility.VISIBLE),
                (x + w, y, KeypointVisibility.VISIBLE),
                (x + w, y + h, KeypointVisibility.VISIBLE),
                (x, y + h, KeypointVisibility.VISIBLE),
            ]

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
                        (float(row["x1"]), float(row["y1"]), KeypointVisibility.VISIBLE),
                        (float(row["x2"]), float(row["y2"]), KeypointVisibility.VISIBLE),
                        (float(row["x3"]), float(row["y3"]), KeypointVisibility.VISIBLE),
                        (float(row["x4"]), float(row["y4"]), KeypointVisibility.VISIBLE),
                    ],
                }
            )
    return detections


def _draw_overlay_on_image(
    img: Image.Image, detections: list[dict], eval_margin_px: int = 0
) -> None:
    """Draw lime edges, crosshairs, winding arrows, and eval margin border.

    Crosshair colour: red = VISIBLE, orange = MARGIN_TRUNCATED. Sentinels skipped.
    """
    from PIL import ImageFont

    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    if eval_margin_px > 0:
        m = eval_margin_px
        w, h = img.size
        draw.rectangle(
            [(m, m), (w - m - 1, h - m - 1)],
            outline="orange",
            width=1,
        )

    for det in detections:
        raw_corners = det["corners"]
        corners_xy = [(c[0], c[1]) for c in raw_corners]
        corner_vis = [c[2] if len(c) > 2 else KeypointVisibility.VISIBLE for c in raw_corners]

        if len(corners_xy) == 4:
            for i in range(4):
                p1 = corners_xy[i]
                p2 = corners_xy[(i + 1) % 4]
                draw.line([p1, p2], fill="lime", width=2)

                mid_x = (p1[0] + p2[0]) / 2
                mid_y = (p1[1] + p2[1]) / 2
                v_x = p2[0] - p1[0]
                v_y = p2[1] - p1[1]
                v_len = (v_x**2 + v_y**2) ** 0.5
                if v_len > 1e-6:
                    v_x /= v_len
                    v_y /= v_len
                    ah_len = 5
                    ah_angle = 0.5
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

        for i, (cx, cy) in enumerate(corners_xy):
            v = corner_vis[i]
            if v == KeypointVisibility.OUT_OF_FRAME:
                continue
            color = "orange" if v == KeypointVisibility.MARGIN_TRUNCATED else "red"
            r = 3
            draw.line([(cx - r, cy), (cx + r, cy)], fill=color, width=1)
            draw.line([(cx, cy - r), (cx, cy + r)], fill=color, width=1)

            if font:
                draw.text((cx + 5, cy + 5), str(i), fill="yellow", font=font)
            else:
                draw.text((cx + 5, cy + 5), str(i), fill="yellow")


def visualize_recipe(recipe_path: Path, output_dir: Path):
    """Load recipe and visualize it in 2D."""
    with open(recipe_path) as f:
        data = json.load(f)

    recipes = data if isinstance(data, list) else [data]
    for item in recipes:
        recipe = SceneRecipe.model_validate(item)
        renderer = ShadowRenderer(recipe)
        renderer.render(output_dir / f"viz_scene_{recipe.scene_id:04d}.png")
