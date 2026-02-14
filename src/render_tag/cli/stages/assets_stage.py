"""
Asset preparation stage for the generation pipeline.
"""

import os
import sys
from pathlib import Path

import typer
from rich.console import Console

from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import get_asset_manager
from render_tag.common.validator import AssetValidator
from render_tag.generation.tags import ensure_tag_asset

console = Console()


class AssetPreparationStage(PipelineStage):
    """Ensures all required assets are present and valid."""

    def execute(self, ctx: GenerationContext) -> None:
        self._ensure_asset_directory()
        self._ensure_specific_tags(ctx)

    def _ensure_asset_directory(self) -> None:
        default_assets_dir = Path(__file__).parents[4] / "assets"
        local_assets_dir = Path(os.environ.get("RENDER_TAG_ASSETS_DIR", default_assets_dir))
        validator = AssetValidator(local_assets_dir)

        if not validator.is_hydrated():
            is_interactive = sys.stdin.isatty()
            if not is_interactive:
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

    def _ensure_specific_tags(self, ctx: GenerationContext) -> None:
        console.print("\n[bold]Ensuring tag assets...[/bold]")
        assets_dir = Path("assets/tags")
        assets_dir.mkdir(parents=True, exist_ok=True)

        scenario = ctx.gen_config.scenario
        families = scenario.tag_families if scenario else [ctx.gen_config.tag.family]
        tags_per_scene = scenario.tags_per_scene[1] if scenario else 1

        for family_enum in families:
            family = family_enum.value
            # Ensure a reasonable number of tags are available
            for i in range(max(tags_per_scene, 10)):
                path = ensure_tag_asset(family, i, assets_dir)
                if ctx.verbose:
                    console.print(f"  [dim]Checked asset:[/dim] {path.name}")
