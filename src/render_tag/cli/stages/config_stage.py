"""
Configuration loading stage for the generation pipeline.
"""

import hashlib
from pathlib import Path

import typer

from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import console
from render_tag.core.schema.job import JobSpec, get_env_fingerprint


class ConfigLoadingStage(PipelineStage):
    """Loads, validates, and prepares the generation configuration."""

    def execute(self, ctx: GenerationContext) -> None:
        # Create output directory early
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        if ctx.resume_from:
            self._load_from_resume(ctx)
        elif ctx.job_spec_path:
            self._load_from_job_spec(ctx)
        else:
            self._load_from_resolver(ctx)

        # Ensure JobSpec is present
        if not ctx.job_spec:
            raise typer.Exit(code=1)

        # Propagate to context
        ctx.gen_config = ctx.job_spec.scene_config

        # Serialize Job Spec to disk
        job_spec_path = ctx.output_dir / "job_spec.json"
        with open(job_spec_path, "w") as f:
            f.write(ctx.job_spec.model_dump_json(indent=2))

        ctx.job_spec_path = job_spec_path
        console.print(f"[green]✓ Job Spec saved to[/green] {job_spec_path}")
        console.print(f"[dim]Job ID:[/dim] {ctx.job_spec.job_id}")

        # Serialize effective config for compatibility (optional, but helper for debugging)
        # We can remove the old job_config_path logic if workers use job-spec.
        # But for now, workers might still expect config.json if we haven't updated them all?
        # The plan says Update Worker to use job-spec.
        # But we still have ctx.job_config_path used?
        # Let's keep it for now as a fallback or debug artifact.

    def _load_from_resume(self, ctx: GenerationContext) -> None:
        console.print(f"[bold blue]Resuming from Job Spec:[/bold blue] {ctx.resume_from}")
        if not ctx.resume_from.exists():
            console.print(f"[bold red]Error:[/bold red] Resume path does not exist: {ctx.resume_from}")
            raise typer.Exit(code=1)

        try:
            ctx.job_spec = JobSpec.from_file(ctx.resume_from)
            self._guard_environment(ctx.job_spec)

            # Important: When resuming, the output_dir is taken from the JobSpec
            ctx.output_dir = ctx.job_spec.paths.output_dir
            ctx.num_scenes = ctx.job_spec.shard_size
            ctx.seed = ctx.job_spec.global_seed

            console.print(f"[green]✓ Resuming job {ctx.job_spec.job_id[:8]}[/green]")
            console.print(f"[dim]Output Directory:[/dim] {ctx.output_dir}")

        except Exception as e:
            console.print(f"[bold red]Error loading resume spec:[/bold red] {e}")
            raise typer.Exit(code=1) from e

    def _load_from_job_spec(self, ctx: GenerationContext) -> None:
        console.print(f"[bold blue]Loading Job Spec:[/bold blue] {ctx.job_spec_path}")
        try:
            with open(ctx.job_spec_path) as f:
                ctx.job_spec = JobSpec.model_validate_json(f.read())

            self._guard_environment(ctx.job_spec)

            # Override context inputs with spec values where applicable
            # (Though context inputs were CLI args...)
            if ctx.num_scenes != 1 and ctx.num_scenes != ctx.job_spec.shard_size:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] --scenes={ctx.num_scenes} ignored. "
                    f"Using job spec value: {ctx.job_spec.shard_size}"
                )
            # Update context
            ctx.num_scenes = ctx.job_spec.shard_size
            ctx.seed = ctx.job_spec.global_seed

            console.print("[green]✓ Job Spec loaded and validated[/green]")

        except Exception as e:
            console.print(f"[bold red]Error loading job spec:[/bold red] {e}")
            raise typer.Exit(code=1) from e

    def _load_from_resolver(self, ctx: GenerationContext) -> None:
        from render_tag.core.config_loader import ConfigResolver

        if ctx.config_path is None:
            ctx.config_path = Path("configs/default.yaml")

        console.print(f"[dim]Resolving config from[/dim] {ctx.config_path}")

        try:
            resolver = ConfigResolver(ctx.config_path)

            # Prepare overrides
            overrides = {}
            if ctx.renderer_mode:
                overrides["renderer_mode"] = ctx.renderer_mode

            seed_arg = "auto"
            if ctx.seed != -1:
                seed_arg = ctx.seed

            ctx.job_spec = resolver.resolve(
                output_dir=ctx.output_dir,
                overrides=overrides,
                seed=seed_arg,
                shard_index=ctx.shard_index if ctx.shard_index != -1 else 0,
                scene_limit=ctx.num_scenes if ctx.num_scenes > 0 else None,
            )

            # Update context with resolved values
            ctx.seed = ctx.job_spec.global_seed
            ctx.num_scenes = ctx.job_spec.shard_size

        except Exception as e:
            console.print(f"[bold red]Error resolving config:[/bold red] {e}")
            raise typer.Exit(code=1) from e

    def _guard_environment(self, job_spec: JobSpec) -> None:
        curr_env_hash, curr_blender_ver = get_env_fingerprint()
        if curr_env_hash != job_spec.env_hash:
            console.print(
                f"[bold red]Validation Error:[/bold red] Environment mismatch (uv.lock).\n"
                f"Spec: {job_spec.env_hash[:8]}\n"
                f"Current: {curr_env_hash[:8]}"
            )
            raise typer.Exit(code=1)

        if curr_blender_ver != job_spec.blender_version:
            console.print(
                f"[bold red]Validation Error:[/bold red] Blender version mismatch.\n"
                f"Spec: {job_spec.blender_version}\n"
                f"Current: {curr_blender_ver}"
            )
            raise typer.Exit(code=1)

        # Integrity Check: Config Hash
        # If the job spec has a config hash, ensure the config inside it matches.
        # This protects against accidental modification of the spec JSON.
        if job_spec.config_hash:
            computed_hash = hashlib.sha256(
                job_spec.scene_config.model_dump_json().encode()
            ).hexdigest()
            if computed_hash != job_spec.config_hash:
                console.print(
                    f"[bold red]Validation Error:[/bold red] Config hash mismatch.\n"
                    f"Spec: {job_spec.config_hash}\n"
                    f"Computed: {computed_hash}"
                )
                raise typer.Exit(code=1)
