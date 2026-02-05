"""
Abstract render execution logic for render-tag.

Provides a pluggable interface for running BlenderProc locally, 
in containers, or via cloud batch systems.
"""

from typing import Protocol, runtime_checkable
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@runtime_checkable
class RenderExecutor(Protocol):
    """Protocol for render execution engines."""
    
    def execute(
        self, 
        recipe_path: Path, 
        output_dir: Path, 
        renderer_mode: str, 
        shard_id: str
    ) -> None:
        """Execute the render for a given recipe.
        
        Args:
            recipe_path: Path to the scene recipe JSON file.
            output_dir: Directory where results should be saved.
            renderer_mode: Blender render engine (cycles, eevee, etc.)
            shard_id: Unique ID for this execution unit.
        """
        ...

class LocalExecutor:
    """Executes renders using local BlenderProc installation."""
    
    def execute(
        self, 
        recipe_path: Path, 
        output_dir: Path, 
        renderer_mode: str, 
        shard_id: str
    ) -> None:
        # Implementation will be migrated from cli.py in next task
        pass

class MockExecutor:
    """No-op executor for testing purposes."""
    
    def execute(
        self, 
        recipe_path: Path, 
        output_dir: Path, 
        renderer_mode: str, 
        shard_id: str
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
