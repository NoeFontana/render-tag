"""
Pre-render statistical auditing for SceneRecipes.

Analyzes the distribution of parameters across many scenes to ensure
diversity and correct sampling behavior without running 3D renders.
"""

import numpy as np
from pydantic import BaseModel
from rich.table import Table

from render_tag.core.schema import SceneRecipe
from render_tag.generation.projection_math import (
    calculate_incidence_angle,
    get_world_matrix,
)


class RecipeAuditReport(BaseModel):
    """Statistical summary of a batch of recipes."""

    scene_count: int
    camera_count: int
    tag_count: int

    distances: dict[str, float]
    angles: dict[str, float]
    lighting_intensities: dict[str, float]
    tags_per_scene: dict[str, float]


class RecipeAuditor:
    """Analyzes a collection of SceneRecipes for statistical sanity."""

    def __init__(self, recipes: list[SceneRecipe]):
        self.recipes = recipes

    def run_audit(self) -> RecipeAuditReport:
        distances = []
        angles = []
        intensities = []
        tag_counts = []
        cam_count = 0
        tag_total = 0

        for recipe in self.recipes:
            intensities.append(recipe.world.lighting.intensity)

            tags = [obj for obj in recipe.objects if obj.type == "TAG"]
            tag_counts.append(len(tags))
            tag_total += len(tags)

            # We assume first tag for distance/angle metrics if multiple tags exist
            target_tag = tags[0] if tags else None

            for cam in recipe.cameras:
                cam_count += 1
                cam_matrix = np.array(cam.transform_matrix)
                cam_loc = cam_matrix[:3, 3]

                if target_tag:
                    # Distance
                    dist = np.linalg.norm(cam_loc - np.array(target_tag.location))
                    distances.append(float(dist))

                    # Angle
                    tag_world_mat = get_world_matrix(
                        target_tag.location, target_tag.rotation_euler, target_tag.scale
                    )
                    angle = calculate_incidence_angle(cam_matrix, tag_world_mat)
                    angles.append(float(angle))

        def get_stats(data) -> dict[str, float]:
            if not data:
                return {"min": 0, "max": 0, "mean": 0, "std": 0}
            arr = np.array(data)
            return {
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
            }

        return RecipeAuditReport(
            scene_count=len(self.recipes),
            camera_count=cam_count,
            tag_count=tag_total,
            distances=get_stats(distances),
            angles=get_stats(angles),
            lighting_intensities=get_stats(intensities),
            tags_per_scene=get_stats(tag_counts),
        )

    @staticmethod
    def render_table(report: RecipeAuditReport) -> Table:
        table = Table(title="Recipe Statistical Audit", box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Min", justify="right")
        table.add_column("Max", justify="right")
        table.add_column("Mean", justify="right")
        table.add_column("Std", justify="right")

        def add_row(name, stats):
            table.add_row(
                name,
                f"{stats['min']:.2f}",
                f"{stats['max']:.2f}",
                f"{stats['mean']:.2f}",
                f"{stats['std']:.2f}",
            )

        add_row("Distance (m)", report.distances)
        add_row("Incidence Angle (deg)", report.angles)
        add_row("Light Intensity", report.lighting_intensities)
        add_row("Tags per Scene", report.tags_per_scene)

        return table
