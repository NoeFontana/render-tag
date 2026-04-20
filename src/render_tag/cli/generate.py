"""
Generation commands using the Pipeline Pattern.
Consolidated stages for radical simplicity.
"""

from pathlib import Path

import typer

from render_tag.cli.pipeline import GenerationContext, GenerationPipeline
from render_tag.cli.stages.config_stage import ConfigLoadingStage
from render_tag.cli.stages.execution_stage import ExecutionStage
from render_tag.cli.stages.final_stage import FinalizationStage
from render_tag.cli.stages.prep_stage import PreparationStage
from render_tag.cli.tools import console
from render_tag.core.config import load_config

app = typer.Typer(help="Generate synthetic data.")


@app.command()
def run(
    config: Path = typer.Option(
        None, "--config", "-c", help="Path to config YAML", resolve_path=True
    ),
    job: Path = typer.Option(None, "--job", help="Path to job.json spec", resolve_path=True),
    output: Path = typer.Option(
        "output/dataset_01", "--output", "-o", help="Output directory", resolve_path=True
    ),
    num_scenes: int = typer.Option(-1, "--scenes", "-n"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    renderer_mode: str | None = typer.Option(None, "--renderer-mode", "-r"),
    workers: int = typer.Option(1, "--workers", "-w"),
    shard_index: int = typer.Option(-1, "--shard-index"),
    total_shards: int = typer.Option(1, "--total-shards"),
    seed: int = typer.Option(
        2026, "--seed", help="Global random seed for deterministic generation"
    ),
    skip_render: bool = typer.Option(False, "--skip-render"),
    executor_type: str = typer.Option("local", "--executor", "-e"),
    resume: bool = typer.Option(False, "--resume"),
    resume_from: Path | None = typer.Option(
        None, "--resume-from", help="Resume an existing job from its spec", resolve_path=True
    ),
    batch_size: int = typer.Option(5, "--batch-size"),
    overrides: list[str] | None = typer.Option(
        None,
        "--override",
        "-D",
        help="Override config value (dot-notation, e.g. camera.fov=90)",
    ),
    presets: list[str] | None = typer.Option(
        None,
        "--preset",
        "-p",
        help=(
            "Apply a named preset (repeatable). Appended after the YAML "
            "`presets:` list so later entries compose on top."
        ),
    ),
) -> None:
    """
    Generate synthetic fiducial marker training data.
    """
    # Parse overrides into a dict
    parsed_overrides = {}
    if overrides:
        for o in overrides:
            if "=" not in o:
                console.print(f"[bold red]Error:[/bold red] Invalid override format: {o}")
                raise typer.Exit(code=1)
            key, value = o.split("=", 1)
            parsed_overrides[key] = value

    # Initialize Context
    ctx = GenerationContext(
        config_path=config,
        job_spec_path=job,
        output_dir=output,
        num_scenes=num_scenes,
        seed=seed,
        shard_index=shard_index,
        total_shards=total_shards,
        verbose=verbose,
        renderer_mode=renderer_mode,
        workers=workers,
        executor_type=executor_type,
        skip_render=skip_render,
        resume=resume,
        resume_from=resume_from,
        batch_size=batch_size,
        overrides=parsed_overrides,
        cli_presets=list(presets or []),
    )

    # Build and Run Pipeline (Consolidated Stages)
    pipeline = (
        GenerationPipeline()
        .add_stage(ConfigLoadingStage())
        .add_stage(PreparationStage())
        .add_stage(ExecutionStage())
        .add_stage(FinalizationStage())
    )

    pipeline.run(ctx)


@app.command(name="validate-config")
def validate_config(
    config: Path = typer.Option(
        "configs/default.yaml",
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Validate a configuration file."""
    console.print(f"[dim]Validating config:[/dim] {config}")
    try:
        gen_config = load_config(config)
        console.print("[bold green]✓ Config is valid![/bold green]")
        console.print(f"  Resolution: {gen_config.camera.resolution}")
        console.print(f"  FOV: {gen_config.camera.fov}°")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@app.command(name="validate-recipe")
def validate_recipe(
    recipe: Path = typer.Option(..., "--recipe", "-r", exists=True, dir_okay=False),
) -> None:
    """Validate a scene recipe explicitly."""
    from render_tag.core.validator import validate_recipe_file

    console.print(f"[dim]Validating recipe:[/dim] {recipe}")
    is_valid, errors, warnings = validate_recipe_file(recipe)

    if warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for w in warnings:
            console.print(w)

    if not is_valid:
        console.print("\n[bold red]Validation Failed:[/bold red]")
        for e in errors:
            console.print(e)
        raise typer.Exit(code=1) from None

    console.print("\n[bold green]✓ Recipe is Valid![/bold green]")
