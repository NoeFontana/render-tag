"""
Abstract render execution logic for render-tag.

Provides a pluggable interface for running BlenderProc locally, 
in containers, or via cloud batch systems.
"""

from typing import Protocol, runtime_checkable
from pathlib import Path
import logging
import subprocess
import sys

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
        
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=not verbose,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Local rendering failed with exit code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output:\n{result.stderr[:1000]}")
            
            # We raise an exception to signal failure to the orchestrator
            raise RuntimeError(f"BlenderProc failed (exit {result.returncode})")

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
        logger.info(f"[MOCK] Executing render: recipe={recipe_path.name}, output={output_dir.name}")

class ExecutorFactory:
    """Factory for creating render executors."""
    
    @staticmethod
    def get_executor(executor_type: str) -> RenderExecutor:
        """Return an instance of the requested executor."""
        if executor_type == "local":
            return LocalExecutor()
        elif executor_type == "mock":
            return MockExecutor()
        else:
            raise ValueError(f"Unknown executor type: {executor_type}")
