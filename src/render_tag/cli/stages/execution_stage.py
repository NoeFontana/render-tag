"""
Execution stage for the generation pipeline.
"""

import subprocess

import typer
from rich.console import Console

from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import check_blenderproc_installed, check_orchestration_installed, console
from render_tag.orchestration.orchestrator import ExecutorFactory, orchestrate


class ExecutionStage(PipelineStage):
    """Executes the rendering process using the selected engine."""

    def execute(self, ctx: GenerationContext) -> None:
        self._check_dependencies(ctx)

        # Local Parallel Manager Mode
        if ctx.workers > 1 and ctx.total_shards == 1:
            console.print(f"[bold]Running Local Parallel Manager ({ctx.workers} workers)[/bold]")
            orchestrate(
                job_spec=ctx.job_spec,
                workers=ctx.workers,
                executor_type=ctx.executor_type,
                resume=ctx.resume,
                batch_size=ctx.batch_size,
                verbose=ctx.verbose,
            )
            return

        if ctx.skip_render:
            console.print("[yellow]--skip-render provided. Skipping Blender launch.[/yellow]")
            return

        # Check if recipes generation was needed?
        # With JobSpec, we might assume executor handles input retrieval.
        # But ValidationStage might have checked recipes?
        # Let's keep existing check if recipes_path is set.
        # But typically orchestration handles recipes.
        # If we are in single worker mode, and pipeline ran generation stage...
        # GenerationStage (not modified yet) produces recipes.

        # Standard Sharded Execution
        try:
            executor = ExecutorFactory.get_executor(ctx.executor_type)
            executor.execute(
                job_spec=ctx.job_spec,
                shard_id=str(ctx.shard_index),
                verbose=ctx.verbose,
            )
            console.print("\n[bold green]✓ Dataset generated successfully![/bold green]")
            self._finalize_results(ctx)

        except subprocess.SubprocessError as e:
            console.print(f"[bold red]Error:[/bold red] Failed to run BlenderProc: {e}")
            raise typer.Exit(code=1) from None
        finally:
            if ctx.job_config_path and ctx.job_config_path.exists():
                ctx.job_config_path.unlink()

    def _check_dependencies(self, ctx: GenerationContext) -> None:
        if not check_orchestration_installed():
            console.print("[bold red]Error:[/bold red] Orchestration dependencies not installed.")
            raise typer.Exit(code=1)

        if (
            ctx.executor_type == "local"
            and not ctx.skip_render
            and not check_blenderproc_installed()
        ):
            console.print("[bold red]Error:[/bold red] blenderproc not installed.")
            raise typer.Exit(code=1)

    def _finalize_results(self, ctx: GenerationContext) -> None:
        # Rename shard files if single shard
        if ctx.total_shards == 1:
            shard_csv = ctx.output_dir / f"tags_shard_{ctx.shard_index}.csv"
            final_csv = ctx.output_dir / "tags.csv"
            if shard_csv.exists():
                shard_csv.rename(final_csv)

            shard_coco = ctx.output_dir / f"coco_shard_{ctx.shard_index}.json"
            final_coco = ctx.output_dir / "annotations.json"
            if shard_coco.exists():
                shard_coco.rename(final_coco)
            else:
                # Fallback search
                others = list(ctx.output_dir.glob("coco_shard_*.json"))
                if others:
                    others[0].rename(final_coco)

        # Summary
        images = list((ctx.output_dir / "images").glob("*.png"))
        console.print(f"[dim]Generated:[/dim] {len(images)} images")
