"""
Execution stage for the generation pipeline.
"""

import subprocess

import typer
from rich.console import Console

from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import check_blenderproc_installed, check_orchestration_installed
from render_tag.orchestration.orchestrator import ExecutorFactory
from render_tag.orchestration.orchestrator import run_local_parallel

console = Console()


class ExecutionStage(PipelineStage):
    """Executes the rendering process using the selected engine."""

    def execute(self, ctx: GenerationContext) -> None:
        self._check_dependencies(ctx)

        # Local Parallel Manager Mode
        if ctx.workers > 1 and ctx.total_shards == 1:
            console.print(f"[bold]Running Local Parallel Manager ({ctx.workers} workers)[/bold]")
            run_local_parallel(
                config_path=ctx.config_path,
                output_dir=ctx.output_dir,
                num_scenes=ctx.num_scenes,
                workers=ctx.workers,
                renderer_mode=ctx.renderer_mode,
                verbose=ctx.verbose,
                executor_type=ctx.executor_type,
                resume=ctx.resume,
                batch_size=ctx.batch_size,
            )
            return

        if ctx.skip_render:
            console.print("[yellow]--skip-render provided. Skipping Blender launch.[/yellow]")
            return

        if not ctx.recipes_path or not ctx.recipes_path.exists():
            return

        # Standard Sharded Execution
        try:
            executor = ExecutorFactory.get_executor(ctx.executor_type)
            executor.execute(
                recipe_path=ctx.recipes_path,
                output_dir=ctx.output_dir,
                renderer_mode=ctx.renderer_mode,
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

        if ctx.executor_type == "local" and not ctx.skip_render:
            if not check_blenderproc_installed():
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
