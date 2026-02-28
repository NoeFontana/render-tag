"""
Preparation stage for the generation pipeline.
Combines asset verification and recipe generation.
"""

import os
import sys
from pathlib import Path

import typer

from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import console, get_asset_manager
from render_tag.core.schema import SceneRecipe
from render_tag.core.validator import AssetValidator, validate_recipe_file
from render_tag.generation.scene import Generator
from render_tag.generation.tags import ensure_tag_asset
from render_tag.orchestration import (
    get_completed_scene_ids,
    resolve_shard_index,
)
from render_tag.orchestration.validator import ShardValidator


class PreparationStage(PipelineStage):
    """Ensures assets are present and generates scene recipes."""

    def execute(self, ctx: GenerationContext) -> None:
        # 1. Assets
        self._ensure_assets(ctx)

        # 2. Sharding / Resuming
        ctx.output_dir = ctx.output_dir.resolve()
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        if ctx.shard_index == -1 and ctx.total_shards > 1:
            ctx.shard_index = resolve_shard_index()
        if ctx.shard_index == -1:
            ctx.shard_index = 0

        # Smart Resumption (Shard-Level)
        if ctx.resume_from:
            validator = ShardValidator(ctx.output_dir)
            scenes_per_shard = ctx.batch_size

            # This call will perform aggressive cleanup if shard is invalid
            is_complete = validator.validate_shard(
                ctx.shard_index,
                expected_scenes=len(ctx.job_spec.get_scene_indices(scenes_per_shard)),
            )

            if is_complete:
                console.print(
                    f"[green]Shard {ctx.shard_index} is already complete. Skipping.[/green]"
                )
                ctx.skip_execution = True
                return

        # Standard Resumption (Scene-Level)
        if ctx.resume:
            ctx.completed_ids = get_completed_scene_ids(ctx.output_dir)
            if ctx.completed_ids:
                console.print(
                    f"[yellow]Resuming. Found {len(ctx.completed_ids)} completed scenes.[/yellow]"
                )

        # 3. Generate Recipes
        console.print(f"[bold]Running Shard {ctx.shard_index + 1}/{ctx.total_shards}[/bold]")
        generator = Generator(
            ctx.gen_config,
            ctx.output_dir,
            global_seed=ctx.seed,
        )

        recipes = generator.generate_shards(
            total_scenes=ctx.num_scenes,
            shard_index=ctx.shard_index,
            total_shards=ctx.total_shards,
            exclude_ids=ctx.completed_ids,
        )

        if not recipes:
            console.print("[yellow]Empty shard range. Exiting.[/yellow]")
            return

        filename = f"recipes_shard_{ctx.shard_index}.json"
        ctx.recipes_path = ctx.output_dir / filename
        generator.save_recipe_json(recipes, filename)
        console.print(f"[dim]Recipe saved to:[/dim] {ctx.recipes_path}")

        # 4. Pre-generate specific tags from recipes
        self._pregenerate_tags(ctx, recipes)

        # 5. Validation
        self._validate_recipes(ctx.recipes_path)

        # 6. Bill of Materials (BoM) Audit
        self._audit_assets(recipes)

    def _pregenerate_tags(self, ctx: GenerationContext, recipes: list[SceneRecipe]) -> None:
        """Scan recipes and pre-generate every required tag PNG in the dataset cache."""
        cache_tag_dir = ctx.output_dir / "cache" / "tags"
        cache_tag_dir.mkdir(parents=True, exist_ok=True)

        required_tags = set()
        for recipe in recipes:
            for obj in recipe.objects:
                if obj.type == "TAG":
                    family = obj.properties.get("tag_family")
                    tag_id = obj.properties.get("tag_id")
                    margin_bits = obj.properties.get("margin_bits", 0)
                    if family and tag_id is not None:
                        required_tags.add((family, tag_id, margin_bits))

        if not required_tags:
            return

        console.print(f"[dim]Pre-generating {len(required_tags)} unique tags...[/dim]")
        for family, tag_id, margin_bits in required_tags:
            ensure_tag_asset(family, tag_id, cache_tag_dir, margin_bits=margin_bits)

    def _ensure_assets(self, ctx: GenerationContext) -> None:
        default_dir = Path(__file__).parents[4] / "assets"
        local_dir = Path(os.environ.get("RENDER_TAG_ASSETS_DIR", default_dir))
        validator = AssetValidator(local_dir)

        if not validator.is_hydrated():
            if not sys.stdin.isatty():
                console.print("[bold red]Error:[/bold red] Required assets missing.")
                raise typer.Exit(code=1)

            console.print("[bold yellow]Warning:[/bold yellow] Assets folder is missing or empty.")
            if typer.confirm("Pull assets from Hugging Face now?", default=True):
                try:
                    get_asset_manager().pull()
                    console.print("[bold green]✓ Assets synchronized![/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Error pulling assets:[/bold red] {e}")
                    raise typer.Exit(code=1) from None
            else:
                raise typer.Exit(code=1)

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

    def _audit_assets(self, recipes: list[SceneRecipe]) -> None:
        """Verify all referenced assets in recipes exist on disk (BoM check)."""
        missing_assets = set()
        total_assets = 0

        for recipe in recipes:
            # Check World Assets
            if recipe.world.background_hdri:
                total_assets += 1
                if not Path(recipe.world.background_hdri).exists():
                    missing_assets.add(recipe.world.background_hdri)

            if recipe.world.texture_path:
                total_assets += 1
                if not Path(recipe.world.texture_path).exists():
                    missing_assets.add(recipe.world.texture_path)

            # Check Object Assets
            for obj in recipe.objects:
                if obj.texture_path:
                    total_assets += 1
                    if not Path(obj.texture_path).exists():
                        missing_assets.add(obj.texture_path)

        if missing_assets:
            console.print("[bold red]Bill of Materials Audit Failed![/bold red]")
            console.print(f"Found {len(missing_assets)} missing asset files.")
            for missing in sorted(missing_assets):
                console.print(f"  [red]MISSING:[/red] {missing}")
            raise typer.Exit(code=1)

        console.print(f"[green]✓ BoM Audit passed ({total_assets} assets verified)[/green]")
