"""
Pipeline Pattern infrastructure for the generation CLI.

Provides a structured way to execute the generation process as a series of
discrete, testable stages.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from render_tag.core.config import GenConfig
from render_tag.core.logging import get_logger
from render_tag.core.schema.job import JobSpec

logger = get_logger(__name__)


@dataclass
class GenerationContext:
    """Shared state passed between pipeline stages."""

    # CLI Inputs
    config_path: Path | None = None
    job_spec_path: Path | None = None
    output_dir: Path = Path("output")
    num_scenes: int = 1
    seed: int = -1
    shard_index: int = -1
    total_shards: int = 1
    verbose: bool = False
    renderer_mode: str = "cycles"
    workers: int = 1
    executor_type: str = "local"
    skip_render: bool = False
    resume: bool = False
    resume_from: Path | None = None
    batch_size: int = 10
    skip_execution: bool = False
    overrides: dict[str, str] = field(default_factory=dict)

    # Intermediate State
    gen_config: GenConfig | None = None
    job_spec: JobSpec | None = None
    final_job_id: str | None = None
    completed_ids: set[int] = field(default_factory=set)
    recipes_path: Path | None = None
    job_config_path: Path | None = None

    # Metadata
    cli_args: list[str] = field(default_factory=list)


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
