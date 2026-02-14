"""
Configuration loading stage for the generation pipeline.
"""

import hashlib
import tempfile
from pathlib import Path

import typer
from rich.console import Console

from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import serialize_config_to_json
from render_tag.core.config import load_config
from render_tag.schema.job import JobSpec, get_env_fingerprint

console = Console()


class ConfigLoadingStage(PipelineStage):
    """Loads, validates, and prepares the generation configuration."""

    def execute(self, ctx: GenerationContext) -> None:
        # Create output directory early
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        if ctx.job_spec_path:
            self._load_from_job_spec(ctx)
        else:
            self._load_from_yaml(ctx)

        # Serialize effective config for workers
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="render_tag_config_"
        ) as tmp:
            ctx.job_config_path = Path(tmp.name)

        serialize_config_to_json(ctx.gen_config, ctx.job_config_path)
        console.print(f"[dim]Job config:[/dim] {ctx.job_config_path}")

    def _load_from_job_spec(self, ctx: GenerationContext) -> None:
        if ctx.config_path is None:
            # Fallback if not provided, though typically required
            ctx.config_path = Path("configs/default.yaml")

        console.print(f"[bold blue]Loading Job Spec:[/bold blue] {ctx.job_spec_path}")
        try:
            with open(ctx.job_spec_path) as f:
                ctx.job_spec = JobSpec.model_validate_json(f.read())

            self._guard_environment(ctx.job_spec)

            # Validate Config Hash
            with open(ctx.config_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()

            if actual_hash != ctx.job_spec.config_hash:
                console.print("[bold red]Error:[/bold red] Config hash mismatch.")
                raise typer.Exit(code=1)

            # Warn if CLI overrides are provided but will be ignored
            # In pipeline context, defaults (like -1) are passed if not set by user
            # We assume -1 means "not set" for seed and shard_index
            if ctx.num_scenes != 1 and ctx.num_scenes != ctx.job_spec.shard_size:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] --scenes={ctx.num_scenes} ignored. "
                    f"Using job spec value: {ctx.job_spec.shard_size}"
                )
            if ctx.seed != -1 and ctx.seed != ctx.job_spec.seed:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] --seed={ctx.seed} ignored. "
                    f"Using job spec value: {ctx.job_spec.seed}"
                )
            if ctx.shard_index != -1 and ctx.shard_index != ctx.job_spec.shard_index:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] --shard-index={ctx.shard_index} ignored. "
                    f"Using job spec value: {ctx.job_spec.shard_index}"
                )

            # Load and Override
            ctx.gen_config = load_config(ctx.config_path)
            ctx.gen_config.dataset.num_scenes = ctx.job_spec.shard_size
            ctx.gen_config.dataset.seeds.global_seed = ctx.job_spec.seed
            ctx.shard_index = ctx.job_spec.shard_index

            # Update context inputs to match spec
            ctx.num_scenes = ctx.job_spec.shard_size
            ctx.seed = ctx.job_spec.seed

            console.print("[green]✓ Job Spec loaded and validated[/green]")

        except Exception as e:
            console.print(f"[bold red]Error loading job spec:[/bold red] {e}")
            raise typer.Exit(code=1) from e

    def _load_from_yaml(self, ctx: GenerationContext) -> None:
        from pydantic import ValidationError

        if ctx.config_path is None:
            ctx.config_path = Path("configs/default.yaml")

        console.print(f"[dim]Loading config from[/dim] {ctx.config_path}")
        try:
            ctx.gen_config = load_config(ctx.config_path)
        except ValidationError as e:
            console.print("[bold red]Validation Error:[/bold red]")
            for err in e.errors():
                loc = ".".join(str(loc_part) for loc_part in err["loc"])
                msg = err["msg"]
                console.print(f"  [cyan]{loc}[/cyan]: {msg}")
            raise typer.Exit(code=1) from None
        except Exception as e:
            console.print(f"[bold red]Error loading config:[/bold red] {e}")
            raise typer.Exit(code=1) from None

        # Apply CLI Overrides
        ctx.gen_config.dataset.num_scenes = ctx.num_scenes
        if ctx.seed != -1:
            ctx.gen_config.dataset.seeds.global_seed = ctx.seed

    def _guard_environment(self, job_spec: JobSpec) -> None:
        curr_env_hash, curr_blender_ver = get_env_fingerprint()
        if curr_env_hash != job_spec.env_hash:
            console.print("[bold red]Error:[/bold red] Environment mismatch (uv.lock).")
            raise typer.Exit(code=1)
        if curr_blender_ver != job_spec.blender_version:
            console.print("[bold red]Error:[/bold red] Blender version mismatch.")
            raise typer.Exit(code=1)
