"""
Generation commands.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import typer
from pydantic import ValidationError

from render_tag.config import load_config
from render_tag.generator import Generator
from render_tag.orchestration.executors import ExecutorFactory
from render_tag.orchestration.sharding import (
    get_completed_scene_ids,
    resolve_shard_index,
    run_local_parallel,
)
from render_tag.tools.validator import AssetValidator, validate_recipe_file

from .tools import (
    check_blenderproc_installed,
    console,
    get_asset_manager,
    serialize_config_to_json,
)

app = typer.Typer(help="Generate synthetic data.")


@app.command()
def run(
    config: Path = typer.Option(
        "configs/default.yaml",
        "--config",
        "-c",
        help="Path to the generation config YAML file",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path = typer.Option(
        "output/dataset_01",
        "--output",
        "-o",
        help="Output directory for generated dataset",
        resolve_path=True,
    ),
    num_scenes: int = typer.Option(
        1,
        "--scenes",
        "-n",
        help="Number of scenes to generate",
        min=1,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output from BlenderProc",
    ),
    renderer_mode: str = typer.Option(
        "cycles",
        "--renderer-mode",
        "-r",
        help="Rendering engine: cycles, workbench, eevee",
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        "-w",
        help="Number of parallel processes",
    ),
    shard_index: int = typer.Option(
        -1,
        "--shard-index",
        help="Index of this shard [0-based]. If -1, auto-detects from Cloud ENV.",
    ),
    total_shards: int = typer.Option(
        1,
        "--total-shards",
        help="Total number of shards (for Cloud/Cluster usage)",
    ),
    seed: int = typer.Option(
        -1,
        "--seed",
        help="Global random seed override",
    ),
    skip_render: bool = typer.Option(
        False,
        "--skip-render",
        help="Only generate recipes, skip Blender rendering",
    ),
    executor_type: str = typer.Option(
        "local",
        "--executor",
        "-e",
        help="Execution engine: local, docker, mock",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Skip already completed scenes by checking sidecar metadata",
    ),
    batch_size: int = typer.Option(
        10,
        "--batch-size",
        help="Number of scenes per worker batch",
    ),
) -> None:
    """
    Generate synthetic fiducial marker training data.

    Launches BlenderProc to render scenes with AprilTags/ArUco markers,
    producing images and corner annotations for detector training.
    """
    # 1. Setup Executor
    executor = ExecutorFactory.get_executor(executor_type)

    # Check for assets (Pre-flight)
    default_assets_dir = Path(__file__).parents[3] / "assets"
    local_assets_dir = Path(os.environ.get("RENDER_TAG_ASSETS_DIR", default_assets_dir))
    asset_validator = AssetValidator(local_assets_dir)
    if not asset_validator.is_hydrated():
        # Check if we are in an interactive session
        is_interactive = sys.stdin.isatty()

        if not is_interactive:
            console.print("[bold red]Error:[/bold red] Required assets missing.")
            console.print("Please run [cyan]render-tag assets pull[/cyan] first.")
            raise typer.Exit(code=1) from None

        console.print("[bold yellow]Warning:[/bold yellow] Assets folder is missing or empty.")
        if typer.confirm("Would you like to pull assets from Hugging Face now?", default=True):
            # Try to pull
            manager = get_asset_manager()
            try:
                # Use HF_TOKEN if available in env
                manager.pull()
                console.print("[bold green]✓ Assets synchronized successfully![/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error pulling assets:[/bold red] {e}")
                console.print("Please run [cyan]render-tag assets pull[/cyan] manually.")
                raise typer.Exit(code=1) from None
        else:
            console.print(
                "[bold red]Error:[/bold red] Required assets missing. Generation may fail."
            )
            raise typer.Exit(code=1) from None

    # Check for blenderproc installation (only if local executor)
    if executor_type == "local" and not check_blenderproc_installed():
        console.print(
            "[bold red]Error:[/bold red] blenderproc is not installed or not in PATH.\n"
            "Install it with: [cyan]pip install blenderproc[/cyan]"
        )
        raise typer.Exit(code=1) from None

    # Load and validate configuration
    console.print(f"[dim]Loading config from[/dim] {config}")
    try:
        gen_config = load_config(config)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config}")
        raise typer.Exit(code=1) from None
    except ValidationError as e:
        console.print("[bold red]Validation Error:[/bold red]")
        for err in e.errors():
            loc = ".".join(str(loc_part) for loc_part in err["loc"])
            msg = err["msg"]
            console.print(f"  [cyan]{loc}[/cyan]: {msg}")
        raise typer.Exit(code=1) from None
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid config: {e}")
        raise typer.Exit(code=1) from None

    # Apply CLI Overrides
    gen_config.dataset.num_scenes = num_scenes
    if seed != -1:
        gen_config.dataset.seeds.global_seed = seed

    # Create output directory
    output.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Output directory:[/dim] {output}")

    # Serialize config to temporary JSON file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        prefix="render_tag_config_",
    ) as tmp_file:
        job_config_path = Path(tmp_file.name)

    serialize_config_to_json(gen_config, job_config_path)
    console.print(f"[dim]Job config:[/dim] {job_config_path}")

    # 1. Resolve Shard Index (Cloud Auto-detect)
    if shard_index == -1 and total_shards > 1:
        shard_index = resolve_shard_index()

    # 2. Identify completed scenes if resuming
    completed_ids = set()
    if resume:
        completed_ids = get_completed_scene_ids(output)
        if completed_ids:
            console.print(
                f"[bold yellow]Resuming run. Found {len(completed_ids)} "
                "completed scenes.[/bold yellow]"
            )

    # 3. Local Parallel (Manager Mode)
    if workers > 1 and total_shards == 1:
        console.print(f"[bold]Running Local Parallel Manager ({workers} workers)[/bold]")
        # Pass resume flag to worker processes
        run_local_parallel(
            config_path=config,
            output_dir=output,
            num_scenes=num_scenes,
            workers=workers,
            renderer_mode=renderer_mode,
            verbose=verbose,
            executor_type=executor_type,
            resume=resume,
            batch_size=batch_size,
        )
        return

    # 3. Worker / Cloud Mode
    if shard_index == -1:
        shard_index = 0  # Default to 0 if single process/worker

    console.print(f"[bold]Running Shard {shard_index + 1}/{total_shards}[/bold]")

    # 1. Generate Scene Recipes (Pure Python)
    console.print("\n[bold]Generating scene recipes...[/bold]")
    generator = Generator(gen_config.model_dump(mode="json"), output)

    # Use Sharded Generation
    recipes = generator.generate_shards(
        total_scenes=num_scenes,
        shard_index=shard_index,
        total_shards=total_shards,
        exclude_ids=completed_ids,
    )

    if not recipes:
        console.print("[yellow]Empty shard range. Exiting.[/yellow]")
        return

    # Unique recipe filename for this shard
    recipe_filename = f"recipes_shard_{shard_index}.json"
    recipe_path = output / recipe_filename
    generator.save_recipe_json(recipes, recipe_filename)
    console.print(f"[dim]Recipe saved to:[/dim] {recipe_path}")

    # Run Pre-Flight Validation
    is_valid, errors, warnings = validate_recipe_file(recipe_path)

    if warnings:
        for w in warnings:
            console.print(f"[yellow]Warning:[/yellow] {w}")

    if not is_valid:
        console.print("[bold red]Pre-flight Validation Failed![/bold red]")
        for e in errors:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    console.print("[green]✓ Pre-flight validation passed[/green]")

    # 2. Ensure tag assets
    from render_tag.tag_gen import ensure_tag_asset

    assets_dir = Path("assets/tags")
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Get families from scenario if present
    scenario = gen_config.scenario
    families = scenario.tag_families if scenario else [gen_config.tag.family]

    tags_per_scene = scenario.tags_per_scene[1] if scenario else 1

    console.print("\n[bold]Ensuring tag assets...[/bold]")
    for family_enum in families:
        family = family_enum.value
        # For simplicity, we ensure a few tags for each family
        for i in range(max(tags_per_scene, 10)):
            asset_path = ensure_tag_asset(family, i, assets_dir)
            if verbose:
                console.print(f"  [dim]Checked asset:[/dim] {asset_path.name}")

    if skip_render:
        console.print("[yellow]--skip-render provided. Skipping Blender launch.[/yellow]")
        return

    try:
        # Run the chosen executor
        executor.execute(
            recipe_path=recipe_path,
            output_dir=output,
            renderer_mode=renderer_mode,
            shard_id=str(shard_index),
            verbose=verbose,
        )

        console.print("\n[bold green]✓ Dataset generated successfully![/bold green]")
        console.print(f"[dim]Output saved to:[/dim] {output}")

        # If running in single-shard mode (standard), rename the shard CSV to tags.csv
        # for simpler usability.
        if total_shards == 1:
            shard_csv = output / f"tags_shard_{shard_index}.csv"
            final_csv = output / "tags.csv"
            if shard_csv.exists():
                shard_csv.rename(final_csv)

        # Show summary of generated files
        images_dir = output / "images"
        if images_dir.exists():
            num_images = len(list(images_dir.glob("*.png")))
            console.print(f"[dim]Generated:[/dim] {num_images} images")

        csv_path = output / "tags.csv"
        if csv_path.exists():
            with open(csv_path) as f:
                num_annotations = sum(1 for _ in f) - 1  # Subtract header
            console.print(f"[dim]Annotations:[/dim] {num_annotations} tag detections")

    except subprocess.SubprocessError as e:
        console.print(f"[bold red]Error:[/bold red] Failed to run BlenderProc: {e}")
        raise typer.Exit(code=1) from None

    finally:
        # Clean up temporary config file
        if job_config_path.exists():
            job_config_path.unlink()

    # Merge Results
    if total_shards == 1:
        # 1. Handle CSV (Find any shard CSV and rename it to tags.csv)
        shard_csvs = list(output.glob("tags_shard_*.csv"))
        if shard_csvs and not (output / "tags.csv").exists():
            shard_csvs[0].rename(output / "tags.csv")
            console.print(f"[dim]Renamed {shard_csvs[0].name} -> tags.csv[/dim]")

        # 2. Handle COCO (annotations.json)
        shard_cocos = list(output.glob("coco_shard_*.json"))
        if shard_cocos and not (output / "annotations.json").exists():
            shard_cocos[0].rename(output / "annotations.json")
            console.print(f"[dim]Renamed {shard_cocos[0].name} -> annotations.json[/dim]")

    console.print("[bold green]✓ Generation session complete[/bold green]")


@app.command(name="validate-config")
def validate_config(
    config: Path = typer.Option(
        "configs/default.yaml",
        "--config",
        "-c",
        help="Path to the config YAML file to validate",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """
    Validate a configuration file without running generation.
    """
    console.print(f"[dim]Validating config:[/dim] {config}")

    try:
        gen_config = load_config(config)
        console.print("[bold green]✓ Config is valid![/bold green]")
        console.print("\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Resolution: {gen_config.camera.resolution}")
        console.print(f"  FOV: {gen_config.camera.fov}°")
        console.print(f"  Tag Family: {gen_config.tag.family.value}")
        console.print(f"  Tag Size: {gen_config.tag.size_meters}m")
        console.print(f"  Samples/Scene: {gen_config.camera.samples_per_scene}")
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config}")
        raise typer.Exit(code=1) from None
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid config: {e}")
        raise typer.Exit(code=1) from None


@app.command(name="validate-recipe")
def validate_recipe(
    recipe: Path = typer.Option(
        ...,
        "--recipe",
        "-r",
        help="Path to the scene recipe JSON file",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """
    Validate a scene recipe explicitly (Pre-Flight Check).

    Checks schema compliance, asset availability, and geometric integrity.
    """
    from render_tag.tools.validator import validate_recipe_file

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
