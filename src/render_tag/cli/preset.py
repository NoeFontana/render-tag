"""CLI: ``render-tag preset`` — introspection for registered presets."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from render_tag.cli.tools import console
from render_tag.core.presets import append_cli_presets, default_registry

app = typer.Typer(help="Preset registry utilities.")


@app.command("list")
def list_presets(
    category: str | None = typer.Option(
        None, "--category", "-c", help="Filter by category (e.g. 'lighting')."
    ),
) -> None:
    """List all registered presets grouped by category."""
    grouped = default_registry.by_category()
    if category:
        if category not in grouped:
            console.print(f"[bold red]Unknown category:[/bold red] {category}")
            raise typer.Exit(code=1)
        grouped = {category: grouped[category]}
    for cat, presets in grouped.items():
        console.print(f"[bold]{cat}[/bold]")
        for preset in presets:
            console.print(f"  [green]{preset.name}[/green]  {preset.description}")


@app.command("show")
def show_preset(
    name: str = typer.Argument(..., help="Dotted preset name, e.g. lighting.factory."),
) -> None:
    """Print the override dict a preset contributes (as YAML)."""
    try:
        preset = default_registry.get(name)
    except KeyError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(code=1) from None
    console.print(f"[bold]{preset.name}[/bold] ({preset.description})")
    console.print(yaml.safe_dump(preset.override(), sort_keys=False).rstrip())


@app.command("resolve")
def resolve(
    config: Path = typer.Option(
        ..., "--config", "-c", exists=True, dir_okay=False, resolve_path=True
    ),
    preset: list[str] | None = typer.Option(
        None, "--preset", "-p", help="Extra preset(s) to append (repeatable)."
    ),
) -> None:
    """Resolve a config + optional CLI presets and print the final YAML."""
    from render_tag.core.config import GenConfig
    from render_tag.core.schema_adapter import adapt_config

    with open(config) as f:
        data = yaml.safe_load(f) or {}
    try:
        append_cli_presets(data, preset)
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(code=1) from None

    resolved = GenConfig.model_validate(adapt_config(data))
    console.print(yaml.safe_dump(resolved.model_dump(mode="json"), sort_keys=False).rstrip())
