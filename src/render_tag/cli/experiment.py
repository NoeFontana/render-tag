"""
Experiment commands.
"""

import subprocess
import sys
from pathlib import Path

import typer

from render_tag.audit.reporting import generate_dataset_info
from render_tag.core.manifest import ChecksumManifest
from render_tag.generation.scene import Generator
from render_tag.generation.tags import ensure_tag_asset
from render_tag.orchestration.experiment import (
    expand_campaign,
    expand_experiment,
    load_experiment_config,
)
from render_tag.orchestration.experiment_schema import Campaign

from .tools import (
    check_blenderproc_installed,
    console,
    serialize_config_to_json,
)

app = typer.Typer(help="Run experiments.")


@app.command(name="run")
def run(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to the experiment configuration YAML file",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path = typer.Option(
        "output/experiments",
        "--output",
        "-o",
        help="Base output directory for experiment results",
        resolve_path=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    renderer_mode: str = typer.Option(
        "cycles",
        "--renderer-mode",
        "-r",
        help="Rendering engine: cycles, workbench, eevee",
    ),
    skip_render: bool = typer.Option(
        False,
        "--skip-render",
        help="Skip the long rendering cycle (Shadow Render only)",
    ),
) -> None:
    """
    Run a controlled experiment (Parameter Sweep).

    Generates multiple datasets based on sweep definitions, keeping other
    variables constant (ceteris paribus).
    """
    # Check dependencies
    if not check_blenderproc_installed():
        console.print("[bold red]Error:[/bold red] blenderproc not installed.")
        raise typer.Exit(code=1) from None

    # Load Experiment
    console.print(f"[dim]Loading experiment from[/dim] {config}")
    try:
        exp_or_campaign = load_experiment_config(config)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Invalid experiment config: {e}")
        raise typer.Exit(code=1) from None

    # Expand Variants
    if isinstance(exp_or_campaign, Campaign):
        # Campaign logic
        # Respect CLI output as base, join with Campaign output_dir
        exp_dir = output / exp_or_campaign.output_dir
        exp_or_campaign.output_dir = str(exp_dir)

        variants = expand_campaign(exp_or_campaign)
        console.print(f"[bold]Found {len(variants)} sub-experiments[/bold] in campaign")
        exp_name = "campaign"

    else:
        # Standard Experiment
        variants = expand_experiment(exp_or_campaign)
        console.print(
            f"[bold]Found {len(variants)} variants[/bold] for experiment '{exp_or_campaign.name}'"
        )
        exp_name = exp_or_campaign.name
        exp_dir = output / exp_name

    exp_dir.mkdir(parents=True, exist_ok=True)

    # Execute Variants
    for i, variant in enumerate(variants):
        console.print(f"\n[bold cyan]Run {i + 1}/{len(variants)}: {variant.variant_id}[/bold cyan]")
        console.print(f"[dim]Description: {variant.description}[/dim]")

        # Determine variant output directory
        if isinstance(exp_or_campaign, Campaign):
            variant_dir = variant.config.dataset.output_dir
        else:
            variant_dir = output / exp_name / variant.variant_id
            variant.config.dataset.output_dir = variant_dir

        variant_dir.mkdir(parents=True, exist_ok=True)

        # 1. Generate Recipes
        generator = Generator(variant.config, variant_dir)
        recipes = generator.generate_all()
        recipe_path = variant_dir / "scene_recipes.json"
        generator.save_recipe_json(recipes, "scene_recipes.json")

        # 2. Save Checksum Manifest (Pre-execution)
        manifest = ChecksumManifest(
            job_id=f"{exp_name}_{variant.variant_id}", output_dir=variant_dir
        )
        # We'll add files AFTER generation, but we can initialize it here.

        # 3. Serialize Config for BlenderProc
        job_config_path = variant_dir / "generation_config.json"
        serialize_config_to_json(variant.config, job_config_path)

        # 4. Ensure Assets (Optimized: only check once? No, easy to check every time)
        scenario = variant.config.scenario
        families = scenario.tag_families if scenario else [variant.config.tag.family]
        assets_dir = Path("assets/tags")
        assets_dir.mkdir(parents=True, exist_ok=True)
        # Assuming we can just ensure generic usage for now
        # Ideally we check what tags are actually in the recipe
        for family_enum in families:
            for j in range(10):  # Arbitrary small number
                ensure_tag_asset(family_enum.value, j, assets_dir)

        # 4.5 Validate Recipes (Shadow Render logic)
        from render_tag.core.validator import validate_recipe_file

        is_valid, errors, warnings = validate_recipe_file(recipe_path)
        if warnings:
            for w in warnings:
                console.print(f"[yellow]Warning:[/yellow] {w}")
        if not is_valid:
            console.print(
                f"[bold red]Recipe Validation Failed for variant {variant.variant_id}![/bold red]"
            )
            for e in errors:
                console.print(f"[red]  - {e}[/red]")
            raise typer.Exit(code=1) from None

        # 5. Run BlenderProc
        if skip_render:
            console.print("[green]Shadow Render Validation Complete (Skip Render enabled).[/green]")
            continue

        # We need to resolve the executor script path relative to the installed package location
        # Assuming render_tag is installed, we find backend/executor.py
        import render_tag.backend

        script_path = Path(render_tag.backend.__file__).parent / "executor.py"
        cmd = [
            "blenderproc",
            "run",
            str(script_path),
            "--recipe",
            str(recipe_path),
            "--output",
            str(variant_dir),
            "--renderer-mode",
            renderer_mode,
        ]

        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=not verbose,
                text=True,
            )
            if result.returncode != 0:
                console.print(f"[bold red]Variant {variant.variant_id} Failed![/bold red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr[:1000]}[/red]")
                # We might want to continue to next variant or stop?
                # Stopping is probably safer for experiments
                raise typer.Exit(code=1) from None

            # 6. Generate Unified Manifest
            generate_dataset_info(
                dataset_dir=variant_dir,
                config=variant.config,
                experiment_info={
                    "name": variant.experiment_name,
                    "variant_id": variant.variant_id,
                    "description": variant.description,
                    "overrides": variant.overrides,
                },
                cli_args=sys.argv,
            )

            # 7. Generate Checksums
            manifest.add_directory(variant_dir / "images", pattern="*.png")
            if (variant_dir / "tags.csv").exists():
                manifest.add_file(variant_dir / "tags.csv")
            manifest.save()

            console.print(f"[green]✓ {variant.variant_id} Complete[/green]")

        except subprocess.SubprocessError as e:
            console.print(f"[bold red]Error running BlenderProc:[/bold red] {e}")
            raise typer.Exit(code=1) from None

    console.print("\n[bold green]Experiment Completed Successfully![/bold green]")
    console.print(f"[dim]Results:[/dim] {exp_dir}")
