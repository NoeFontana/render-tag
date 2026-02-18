
from __future__ import annotations
from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from render_tag.cli.pipeline import GenerationContext
    from render_tag.core.schema.recipe import ObjectRecipe

@runtime_checkable
class SubjectStrategy(Protocol):
    """Protocol for subject-specific generation logic.
    
    Decouples the SceneCompiler from domain-specific logic like tag scattering
    or calibration board layout.
    """

    def prepare_assets(self, context: GenerationContext) -> None:
        """Generate or load assets required for the subject.
        
        This might include synthetic texture generation (for boards)
        or ensuring mesh assets are available.
        """
        ...

    def sample_pose(self, seed: int, context: GenerationContext) -> list[ObjectRecipe]:
        """Generate a list of objects with resolved poses for a single scene.
        
        Args:
            seed: Scene-specific random seed.
            context: Shared generation context.
            
        Returns:
            A list of ObjectRecipe instructions for the renderer.
        """
        ...
