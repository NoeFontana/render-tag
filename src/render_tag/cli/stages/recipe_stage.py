"""
Recipe generation and validation stage.
"""

import typer
from rich.console import Console

from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.common.validator import validate_recipe_file
from render_tag.generation.scene import Generator
from render_tag.orchestration.orchestrator_utils import (
    get_completed_scene_ids,
    resolve_shard_index,
)

console = Console()


class RecipeGenerationStage(PipelineStage):
    """Generates and validates scene recipes for the current shard."""

    def execute(self, ctx: GenerationContext) -> None:
        # 1. Resolve Shard Index
        if ctx.shard_index == -1 and ctx.total_shards > 1:
            ctx.shard_index = resolve_shard_index()
        if ctx.shard_index == -1:
            ctx.shard_index = 0

        # 2. Identify Completed Scenes
        if ctx.resume:
            ctx.completed_ids = get_completed_scene_ids(ctx.output_dir)
            if ctx.completed_ids:
                console.print(
                    f"[bold yellow]Resuming. Found {len(ctx.completed_ids)} completed scenes.[/bold yellow]"
                )

        # 3. Generate Recipes
        console.print(f"[bold]Running Shard {ctx.shard_index + 1}/{ctx.total_shards}[/bold]")
        generator = Generator(ctx.gen_config.model_dump(mode="json"), ctx.output_dir)

        recipes = generator.generate_shards(
            total_scenes=ctx.num_scenes,
            shard_index=ctx.shard_index,
            total_shards=ctx.total_shards,
            exclude_ids=ctx.completed_ids,
        )

        if not recipes:
            console.print("[yellow]Empty shard range. Exiting.[/yellow]")
            # We don't raise Exit here, just return early to skip execution
            return

        filename = f"recipes_shard_{ctx.shard_index}.json"
        ctx.recipes_path = ctx.output_dir / filename
        generator.save_recipe_json(recipes, filename)
        console.print(f"[dim]Recipe saved to:[/dim] {ctx.recipes_path}")

        # 4. Pre-Flight Validation
        self._validate_recipes(ctx.recipes_path)

    def _validate_recipes(self, path) -> None:
        is_valid, errors, warnings = validate_recipe_file(path)

        if warnings:
            for w in warnings:
                console.print(f"[yellow]Warning:[/yellow] {w}")

        if not is_valid:
            console.print("[bold red]Pre-flight Validation Failed![/bold red]")
            for e in errors:
                console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)

        console.print("[green]✓ Pre-flight validation passed[/green]")
