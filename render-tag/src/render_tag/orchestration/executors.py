"""
Abstract render execution logic for render-tag.

Provides a pluggable interface for running BlenderProc locally, 
in containers, or via cloud batch systems.
"""

from typing import Protocol, runtime_checkable, List
from pathlib import Path
import logging
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

# Global list for tracking active render processes
_active_render_processes: List[subprocess.Popen] = []

def cleanup_render_processes():
    """Kill all tracked render processes."""
    for p in _active_render_processes:
        if p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
    time.sleep(0.2)
    for p in _active_render_processes:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
    _active_render_processes.clear()

@runtime_checkable
class RenderExecutor(Protocol):
    """Protocol for render execution engines."""
    
    def execute(
        self, 
        recipe_path: Path, 
        output_dir: Path, 
        renderer_mode: str, 
        shard_id: str,
        verbose: bool = False
    ) -> None:
        """Execute the render for a given recipe.
        
        Args:
            recipe_path: Path to the scene recipe JSON file.
            output_dir: Directory where results should be saved.
            renderer_mode: Blender render engine (cycles, eevee, etc.)
            shard_id: Unique ID for this execution unit.
            verbose: If True, show BlenderProc output.
        """
        ...

class LocalExecutor:
    """Executes renders using local BlenderProc installation."""
    
    def execute(
        self, 
        recipe_path: Path, 
        output_dir: Path, 
        renderer_mode: str, 
        shard_id: str,
        verbose: bool = False
    ) -> None:
        # Find the backend executor script relative to this file
        # src/render_tag/orchestration/executors.py -> src/render_tag/backend/executor.py
        script_path = Path(__file__).parent.parent / "backend" / "executor.py"
        
        if not script_path.exists():
            raise FileNotFoundError(f"Backend executor script not found at {script_path}")

        cmd = [
            "blenderproc",
            "run",
            str(script_path),
            "--recipe",
            str(recipe_path),
            "--output",
            str(output_dir),
            "--renderer-mode",
            renderer_mode,
            "--shard-id",
            str(shard_id),
        ]

        logger.info(f"Launching local BlenderProc: {' '.join(cmd)}")
        
        p = subprocess.Popen(
            cmd,
            stdout=None if verbose else subprocess.PIPE,
            stderr=None if verbose else subprocess.PIPE,
            text=True,
        )
        _active_render_processes.append(p)

        try:
            stdout, stderr = p.communicate()
            if p.returncode != 0:
                logger.error(f"Local rendering failed with exit code {p.returncode}")
                if stderr:
                    logger.error(f"Error output:\n{stderr[:1000]}")
                raise RuntimeError(f"BlenderProc failed (exit {p.returncode})")
        finally:
            if p in _active_render_processes:
                _active_render_processes.remove(p)

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
        verbose: bool = False
    ) -> None:
        # We need absolute paths for Docker volume mapping
        abs_output = output_dir.absolute()
        abs_recipe = recipe_path.absolute()
        
        # We mount the output directory to /output inside the container
        # We also mount the recipe file
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{abs_output}:/output",
            "-v", f"{abs_recipe}:/recipe.json",
            self.image,
            "blenderproc", "run", "src/render_tag/backend/executor.py",
            "--recipe", "/recipe.json",
            "--output", "/output",
            "--renderer-mode", renderer_mode,
            "--shard-id", shard_id
        ]

        logger.info(f"Launching Docker BlenderProc: {' '.join(cmd)}")
        
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
        verbose: bool = False
    ) -> None:
        print(f"[MOCK] Executing render: recipe={recipe_path.name}, output={output_dir.name}")

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
