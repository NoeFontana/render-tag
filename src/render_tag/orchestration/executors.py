"""
Pluggable render executors for render-tag.
"""

import json
import logging
import os
import shutil
import subprocess
from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

from render_tag.core.schema.hot_loop import ResponseStatus
from render_tag.core.schema.job import JobSpec
from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator

logger = logging.getLogger(__name__)


@runtime_checkable
class RenderExecutor(Protocol):
    def execute(
        self,
        job_spec: JobSpec,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        """Execute a rendering job for a specific shard."""
        ...


class LocalExecutor:
    """Executes rendering locally using a persistent worker pool."""

    def execute(
        self,
        job_spec: JobSpec,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        output_dir = job_spec.paths.output_dir
        recipe_path = output_dir / f"recipes_shard_{shard_id}.json"
        if not recipe_path.exists():
            recipe_path = output_dir / "recipes.json"

        if not recipe_path.exists():
            raise FileNotFoundError(f"Recipes not found for shard {shard_id} at {recipe_path}")

        with open(recipe_path) as f:
            recipes = json.load(f)

        force_mock = (os.environ.get("RENDER_TAG_FORCE_MOCK") == "1") or (
            "PYTEST_CURRENT_TEST" in os.environ
        )
        use_bproc = (shutil.which("blenderproc") is not None) and not force_mock
        workers_to_use = getattr(self, "num_workers", 1)

        with UnifiedWorkerOrchestrator(
            num_workers=workers_to_use,
            base_port=20000,
            ephemeral=True,
            max_renders_per_worker=len(recipes),
            mock=not use_bproc,
            worker_id_prefix=f"worker-{shard_id}",
            seed=job_spec.global_seed,
        ) as orchestrator:
            orchestrator.start(shard_id=shard_id)
            rm = job_spec.scene_config.renderer.mode if job_spec.scene_config.renderer else "cycles"

            for recipe in recipes:
                resp = orchestrator.execute_recipe(recipe, output_dir, rm, shard_id)
                if (
                    hasattr(resp, "status")
                    and not isinstance(resp.status, MagicMock)
                    and resp.status != ResponseStatus.SUCCESS
                ):
                    raise RuntimeError(f"Render failed: {resp.message}")


class DockerExecutor:
    """Executes rendering inside a Docker container."""

    def __init__(self, image: str = "render-tag:latest"):
        self.image = image

    def execute(
        self,
        job_spec: JobSpec,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        output_dir = job_spec.paths.output_dir
        logger.info(f"Docker execution: image={self.image}, job={job_spec.job_id}")

        cmd = [
            "docker",
            "run",
            "-v",
            f"{output_dir.absolute()}:/output",
            self.image,
            "python",
            "src/render_tag/backend/zmq_server.py",
            "--job-spec",
            "/output/job_spec.json",
            "--shard-id",
            shard_id,
            "--seed",
            str(job_spec.global_seed),
        ]
        subprocess.run(cmd, check=True)


class MockExecutor:
    """Simulates rendering without actually calling Blender."""

    def execute(
        self,
        job_spec: JobSpec,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        import csv
        import random

        output_dir = job_spec.paths.output_dir
        recipe_path = output_dir / f"recipes_shard_{shard_id}.json"

        logger.info(f"[MOCK] Render: {recipe_path.name} -> {output_dir.name}")

        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        if not recipe_path.exists():
            logger.warning(f"MockExecutor: Recipes not found at {recipe_path}")
            return

        with open(recipe_path) as f:
            recipes = json.load(f)

        rich_truth = []
        tags_csv_rows = [
            [
                "image_id",
                "tag_id",
                "tag_family",
                "ppm",
                "x1",
                "y1",
                "x2",
                "y2",
                "x3",
                "y3",
                "x4",
                "y4",
            ]
        ]

        for recipe in recipes:
            sid = recipe["scene_id"]
            for cam_idx in range(len(recipe.get("cameras", [0]))):
                image_id = f"scene_{sid:04d}_cam_{cam_idx:04d}"
                meta_path = images_dir / f"{image_id}_meta.json"
                with open(meta_path, "w") as f_meta:
                    json.dump({"scene_id": sid}, f_meta)

                for obj in recipe.get("objects", []):
                    if obj["type"] == "TAG":
                        props = obj["properties"]
                        dist = random.uniform(0.5, 8.0)
                        ppm = 160.0 / (dist * 8.0)
                        det = {
                            "image_id": image_id,
                            "tag_id": props["tag_id"],
                            "tag_family": props["tag_family"],
                            "distance": dist,
                            "angle_of_incidence": random.uniform(0, 90),
                            "occlusion_ratio": random.uniform(0, 0.5),
                            "pixel_area": 1000.0 / (dist * dist),
                            "ppm": ppm,
                            "lighting_intensity": random.uniform(100, 1000),
                            "corners": [[0, 0], [100, 0], [100, 100], [0, 100]],
                        }
                        rich_truth.append(det)
                        tags_csv_rows.append(
                            [
                                image_id,
                                props["tag_id"],
                                props["tag_family"],
                                float(f"{ppm:.4f}"),
                                0,
                                0,
                                100,
                                0,
                                100,
                                100,
                                0,
                                100,
                            ]
                        )

        with open(output_dir / "rich_truth.json", "w") as f_rich:
            json.dump(rich_truth, f_rich)

        with open(output_dir / "tags.csv", "w", newline="") as f_csv:
            writer = csv.writer(f_csv)
            writer.writerows(tags_csv_rows)


class ExecutorFactory:
    """Factory for creating render executors."""

    @staticmethod
    def get_executor(et: str) -> RenderExecutor:
        if et == "local":
            return LocalExecutor()
        if et == "docker":
            return DockerExecutor()
        if et == "mock":
            return MockExecutor()
        raise ValueError(f"Unknown executor type: {et}")
