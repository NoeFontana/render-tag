"""
Pipeline Pattern infrastructure for the generation CLI.

Provides a structured way to execute the generation process as a series of
discrete, testable stages.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from render_tag.core.logging import get_logger
from render_tag.generation.context import GenerationContext

logger = get_logger(__name__)

# Re-export for backwards compatibility
__all__ = ["GenerationContext", "GenerationPipeline", "PipelineStage"]


class PipelineStage(ABC):
    """Abstract base class for a single stage in the generation pipeline."""

    @abstractmethod
    def execute(self, ctx: GenerationContext) -> None:
        """
        Execute the stage logic.

        Args:
            ctx: The shared generation context.
        """
        ...


class GenerationPipeline:
    """Executes a sequence of stages."""

    def __init__(self):
        self.stages: list[PipelineStage] = []

    def add_stage(self, stage: PipelineStage) -> GenerationPipeline:
        self.stages.append(stage)
        return self

    def run(self, ctx: GenerationContext) -> None:
        """Run all stages in order."""
        for stage in self.stages:
            stage_name = stage.__class__.__name__
            logger.debug("Starting stage", stage=stage_name)
            stage.execute(ctx)
            logger.debug("Finished stage", stage=stage_name)
