from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from render_tag.generation.context import GenerationContext
    from render_tag.core.schema.recipe import ObjectRecipe


@runtime_checkable
class SubjectStrategy(Protocol):
    """Protocol for subject-specific generation logic.

    This interface decouples the high-level scene compilation loop from the
    domain-specific details of different subjects (e.g., individual tags vs.
    rigid calibration boards). It follows the Strategy pattern to allow
    maximum extensibility.
    """

    def prepare_assets(self, context: GenerationContext) -> None:
        """Generate or resolve persistent assets required for this subject.

        This method is called once per generation job (or shard) to perform
        expensive operations like synthetic texture synthesis or mesh discovery.
        Results should be cached or stored in the context/strategy state.

        Args:
            context: The shared generation context containing configuration
                and output directory information.
        """
        ...

    def sample_pose(self, seed: int, context: GenerationContext) -> list[ObjectRecipe]:
        """Generate subject objects with resolved poses for a single scene.

        Responsible for calculating the 3D position, rotation, and scale of all
        objects comprising the subject, as well as providing 3D keypoints for
        ground-truth projection.

        Args:
            seed: A deterministic random seed specific to this scene.
            context: The shared generation context.

        Returns:
            A list of ObjectRecipe instances ready for the rendering backend.
        """
        ...
