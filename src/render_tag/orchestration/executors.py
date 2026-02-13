"""
Abstract render execution logic for render-tag.

Provides a pluggable interface for running BlenderProc locally,
in containers, or via cloud batch systems.
"""

import json
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from render_tag.orchestration.unified_orchestrator import UnifiedWorkerOrchestrator
from render_tag.schema.hot_loop import ResponseStatus

logger = logging.getLogger(__name__)


@runtime_checkable
class RenderExecutor(Protocol):
    """Protocol for render execution engines."""

    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        """Execute the render for a given recipe."""
        ...


class LocalExecutor:
    """
    Executes renders locally using the UnifiedWorkerOrchestrator in ephemeral mode.
    Retires the legacy subprocess-per-shard logic.
    """

    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        logger.info(f"Executing local render shard {shard_id} via Unified Orchestrator.")

        with open(recipe_path) as f:
            recipes = json.load(f)

        # Launch an ephemeral pool for this shard
        # base_port is offset by a hash of shard_id to avoid conflicts in parallel runs
        import hashlib

        port_offset = int(hashlib.md5(shard_id.encode()).hexdigest(), 16) % 1000

        # Check if blenderproc is available, otherwise use mock mode
        # Staff Engineer: Also allow forced mock via environment variable for CI/Testing
        import os
        import shutil

        force_mock = os.environ.get("RENDER_TAG_FORCE_MOCK") == "1"
        use_bproc = (shutil.which("blenderproc") is not None) and not force_mock

        if force_mock:
            logger.info("Forcing MOCK mode via RENDER_TAG_FORCE_MOCK.")
        elif not use_bproc:
            logger.warning(
                "blenderproc not found in PATH. Falling back to MOCK mode for LocalExecutor."
            )

        with UnifiedWorkerOrchestrator(
            num_workers=1,
            base_port=8000 + port_offset,
            ephemeral=True,
            max_renders_per_worker=len(recipes),
            use_blenderproc=use_bproc,
            mock=not use_bproc,
        ) as orchestrator:
            for recipe in recipes:
                # Staff Engineer: Pass shard_id to ensure artifacts are named correctly
                # so the CLI can find and aggregate them.
                resp = orchestrator.execute_recipe(
                    recipe, output_dir, renderer_mode, shard_id=shard_id
                )
                if resp.status != ResponseStatus.SUCCESS:
                    raise RuntimeError(f"Render failed: {resp.message}")


class DockerExecutor:
    """Executes renders inside a Docker container."""

    def __init__(self, image: str = "render-tag:latest"):
        self.image = image

    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        abs_output = output_dir.absolute()
        abs_recipe = recipe_path.absolute()

        cmd = [
            "docker",
            "run",
            "--rm",
            "-e",
            "PYTHONNOUSERSITE=1",
            "-v",
            f"{abs_output}:/output",
            "-v",
            f"{abs_recipe}:/recipe.json",
            self.image,
            "blenderproc",
            "run",
            "src/render_tag/backend/executor.py",
            "--recipe",
            "/recipe.json",
            "--output",
            "/output",
            "--renderer-mode",
            renderer_mode,
            "--shard-id",
            shard_id,
        ]

        logger.info(f"Launching Docker BlenderProc: {' '.join(cmd)}")
        import subprocess

        result = subprocess.run(
            cmd,
            check=False,
            capture_output=not verbose,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Docker rendering failed with exit code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output:\n{result.stderr[:1000]}")
            raise RuntimeError(f"Docker execution failed (exit {result.returncode})")


class MockExecutor:
    """No-op executor for testing purposes."""

    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        logger.info(f"[MOCK] Executing render: recipe={recipe_path.name}, output={output_dir.name}")


class ExecutorFactory:
    """Factory for creating render executors."""

    @staticmethod
    def get_executor(executor_type: str) -> RenderExecutor:
        """Return an instance of the requested executor."""
        if executor_type == "local":
            return LocalExecutor()
        elif executor_type == "docker":
            return DockerExecutor()
        elif executor_type == "mock":
            return MockExecutor()
        else:
            raise ValueError(f"Unknown executor type: {executor_type}")
