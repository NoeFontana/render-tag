"""
Generation context shared between pipeline stages and strategies.

Extracted from cli.pipeline to avoid circular imports between
generation/ and cli/ layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from render_tag.core.config import GenConfig
from render_tag.core.schema.job import JobSpec


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
