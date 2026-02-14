"""
Pipeline Pattern infrastructure for the generation CLI.

Provides a structured way to execute the generation process as a series of
discrete, testable stages.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from render_tag.core.config import GenConfig
from render_tag.schema.job import JobSpec

logger = logging.getLogger(__name__)


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
    batch_size: int = 10

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

    def add_stage(self, stage: PipelineStage) -> "GenerationPipeline":
        self.stages.append(stage)
        return self

    def run(self, ctx: GenerationContext) -> None:
        """Run all stages in order."""
        for stage in self.stages:
            stage_name = stage.__class__.__name__
            logger.debug(f"Starting stage: {stage_name}")
            stage.execute(ctx)
            logger.debug(f"Finished stage: {stage_name}")
