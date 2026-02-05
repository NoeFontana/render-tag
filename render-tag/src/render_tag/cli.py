"""
CLI Orchestrator for render-tag synthetic data generation.

This module runs in the standard system Python environment and manages
the BlenderProc subprocess for rendering.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from .config import GenConfig, load_config
from .data_io.visualization import visualize_dataset, visualize_recipe
from .generator import Generator
from .orchestration.executors import ExecutorFactory
from .orchestration.sharding import resolve_shard_index, run_local_parallel, get_completed_scene_ids
from .tools.validator import validate_recipe_file, AssetValidator
from .orchestration.assets import AssetManager

app = typer.Typer(
    name="render-tag",
    help="3D Procedural Synthetic Data Generation for Fiducial Markers",
    add_completion=False,
)
assets_app = typer.Typer(help="Manage binary assets (HDRIs, Textures, etc.)")
app.add_typer(assets_app, name="assets")

console = Console()


def get_asset_manager() -> AssetManager:
    """Helper to initialize AssetManager with local directory."""
    # Assets folder is at the root of the project by default
    # but can be overridden by environment variable
    default_dir = Path(__file__).parents[2] / "assets"
    local_dir = Path(os.environ.get("RENDER_TAG_ASSETS_DIR", default_dir))
    return AssetManager(local_dir=local_dir)


@assets_app.command()
def pull(
    token: str = typer.Option(
        None,
        envvar="HF_TOKEN",
        help="Hugging Face API token",
    ),
) -> None:
    """
    Download the latest assets from Hugging Face.
    """
    manager = get_asset_manager()
    console.print(f"[bold]Pulling assets from {manager.repo_id}...[/bold]")
    try:
        manager.pull(token=token)
        console.print("[bold green]✓ Assets synchronized successfully![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@assets_app.command()
def push(
    message: str = typer.Option(
        "Update assets",
        "--message",
        "-m",
        help="Semantic commit message for the asset update",
    ),
    token: str = typer.Option(
        None,
        envvar="HF_TOKEN",
        help="Hugging Face API token (required for write access)",
    ),
) -> None:
    """
    Upload local asset changes to Hugging Face.
    """
    if not token:
        console.print("[bold red]Error:[/bold red] HF_TOKEN is required for pushing assets.")
        raise typer.Exit(code=1) from None

    manager = get_asset_manager()
    console.print(f"[bold]Pushing assets to {manager.repo_id}...[/bold]")
    try:
        manager.push(token=token, commit_message=message)
        console.print("[bold green]✓ Assets uploaded successfully![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None


def check_blenderproc_installed() -> bool:
    """Check if blenderproc is available in the system."""
    return shutil.which("blenderproc") is not None


def serialize_config_to_json(config: GenConfig, output_path: Path) -> None:
    """Serialize the validated config to JSON for the Blender subprocess.

    Args:
        config: Validated GenConfig instance
        output_path: Path to write the JSON file
    """
    # Convert Pydantic model to dict, handling Path objects
    config_dict = config.model_dump(mode="json")

    with open(output_path, "w") as f:
        json.dump(config_dict, f, indent=2, default=str)


@app.command()
def generate(
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
    console.print(
        Panel.fit(
            "[bold blue]render-tag[/bold blue] Synthetic Data Generator",
            border_style="blue",
        )
    )

    # 1. Setup Executor
    executor = ExecutorFactory.get_executor(executor_type)

    # Check for assets (Pre-flight)
    default_assets_dir = Path(__file__).parents[2] / "assets"
    local_assets_dir = Path(os.environ.get("RENDER_TAG_ASSETS_DIR", default_assets_dir))
    asset_validator = AssetValidator(local_assets_dir)
    if not asset_validator.is_hydrated():
        # Check if we are in an interactive session
        import sys
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
            console.print("[bold red]Error:[/bold red] Required assets missing. Generation may fail.")
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
            loc = ".".join(str(l) for l in err["loc"])
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
            console.print(f"[bold yellow]Resuming run. Found {len(completed_ids)} completed scenes.[/bold yellow]")

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
            resume=resume,  # New parameter
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

    # 2. Ensure tag assets (as before)
    from .tag_gen import ensure_tag_asset

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
        # In a more advanced version, we'd use the specific IDs requested
        for i in range(max(tags_per_scene, 10)):
            asset_path = ensure_tag_asset(family, i, assets_dir)
            if verbose:
                console.print(f"  [dim]Checked asset:[/dim] {asset_path.name}")

    # Build the blenderproc command
    script_path = Path(__file__).parent / "backend" / "executor.py"

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

        if job_config_path.exists():
            job_config_path.unlink()

    # Merge Results
    if total_shards == 1:
        # In single shard mode, executor might have output tags_shard_0.csv
        # We handle this in the executor or here?
        # Actually executor.py in single-shard mode outputs tags_shard_0.csv
        # CLI expects tags.csv.
        shard_csv = output / "tags_shard_0.csv"
        if shard_csv.exists() and not (output / "tags.csv").exists():
            shard_csv.rename(output / "tags.csv")
            console.print("[dim]Renamed tags_shard_0.csv -> tags.csv[/dim]")

    console.print("[bold green]✓ Generation session complete[/bold green]")


@app.command()
def experiment(
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
) -> None:
    """
    Run a controlled experiment (Parameter Sweep).

    Generates multiple datasets based on sweep definitions, keeping other
    variables constant (ceteris paribus).
    """
    import sys

    from render_tag.orchestration.experiment import (
        expand_experiment,
        load_experiment_config,
        save_manifest,
    )

    console.print(
        Panel.fit(
            "[bold blue]render-tag[/bold blue] Experiment Runner",
            border_style="blue",
        )
    )

    # Check dependencies
    if not check_blenderproc_installed():
        console.print("[bold red]Error:[/bold red] blenderproc not installed.")
        raise typer.Exit(code=1) from None

    # Load Experiment
    console.print(f"[dim]Loading experiment from[/dim] {config}")
    try:
        exp = load_experiment_config(config)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Invalid experiment config: {e}")
        raise typer.Exit(code=1) from None

    # Expand Variants
    variants = expand_experiment(exp)
    console.print(f"[bold]Found {len(variants)} variants[/bold] for experiment '{exp.name}'")

    # Prepare Base Output
    exp_dir = output / exp.name
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Execute Variants
    for i, variant in enumerate(variants):
        console.print(f"\n[bold cyan]Run {i + 1}/{len(variants)}: {variant.variant_id}[/bold cyan]")
        console.print(f"[dim]Description: {variant.description}[/dim]")

        variant_dir = exp_dir / variant.variant_id
        variant_dir.mkdir(exist_ok=True)

        # Update config output dir for this variant
        # (Generator takes output_dir explicitly, setting it in config is for consistency)
        variant.config.dataset.output_dir = variant_dir

        # 1. Generate Recipes
        generator = Generator(variant.config, variant_dir)
        recipes = generator.generate_all()
        recipe_path = variant_dir / "scene_recipes.json"
        generator.save_recipe_json(recipes, "scene_recipes.json")

        # 2. Save Manifest
        save_manifest(variant_dir, variant, cli_args=sys.argv)

        # 3. Serialize Config for BlenderProc
        job_config_path = variant_dir / "generation_config.json"
        serialize_config_to_json(variant.config, job_config_path)

        # 4. Ensure Assets (Optimized: only check once? No, easy to check every time)
        from .tag_gen import ensure_tag_asset

        scenario = variant.config.scenario
        families = scenario.tag_families if scenario else [variant.config.tag.family]
        assets_dir = Path("assets/tags")
        assets_dir.mkdir(parents=True, exist_ok=True)
        # Assuming we can just ensure generic usage for now
        # Ideally we check what tags are actually in the recipe
        for family_enum in families:
            for j in range(10):  # Arbitrary small number
                ensure_tag_asset(family_enum.value, j, assets_dir)

        # 5. Run BlenderProc
        script_path = Path(__file__).parent / "backend" / "executor.py"
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

            console.print(f"[green]✓ {variant.variant_id} Complete[/green]")

        except subprocess.SubprocessError as e:
            console.print(f"[bold red]Error running BlenderProc:[/bold red] {e}")
            raise typer.Exit(code=1) from None

    console.print(f"\n[bold green]Experiment '{exp.name}' Completed Successfully![/bold green]")
    console.print(f"[dim]Results:[/dim] {exp_dir}")


@app.command()
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


@app.command()
def info() -> None:
    """
    Show information about the render-tag installation.
    """
    console.print("[bold]render-tag[/bold] - Synthetic Data Generator for Fiducial Markers\n")

    # Check blenderproc
    if check_blenderproc_installed():
        console.print("[green]✓[/green] blenderproc is installed")
        # Try to get version
        try:
            result = subprocess.run(
                ["blenderproc", "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print(f"  Version: {result.stdout.strip()}")
        except Exception:
            pass
    else:
        console.print("[red]✗[/red] blenderproc is NOT installed")

    # Show supported tag families
    from .config import TagFamily

    console.print("\n[bold]Supported Tag Families:[/bold]")
    apriltags = [t for t in TagFamily if t.is_apriltag]
    arucos = [t for t in TagFamily if t.is_aruco]
    console.print(f"  AprilTag: {len(apriltags)} families")
    console.print(f"  ArUco: {len(arucos)} dictionaries")


@app.command()
def viz_recipe(
    recipe: Path = typer.Option(
        ...,
        "--recipe",
        "-r",
        help="Path to the scene recipe JSON file",
        exists=True,
        dir_okay=False,
    ),
    output: Path = typer.Option(
        "output/viz",
        "--output",
        "-o",
        help="Output directory for visualizations",
    ),
) -> None:
    """
    Visualize a scene recipe in 2D (Shadow Render).

    Generates a top-down view of the layout for verification.
    """
    output.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Visualizing recipe:[/dim] {recipe}")

    try:
        visualize_recipe(recipe, output)
        console.print(f"[bold green]✓ Visualization saved to:[/bold green] {output}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Visualization failed: {e}")
        raise typer.Exit(code=1) from None


@app.command()
def viz(
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to the dataset output directory",
        exists=True,
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
    ),
    image: str = typer.Option(
        None,
        "--image",
        "-i",
        help="Specific image ID to visualize (without extension)",
    ),
    no_save: bool = typer.Option(
        False,
        "--no-save",
        help="Don't save visualization images",
    ),
) -> None:
    """
    Visualize detection annotations overlaid on rendered images.
    """
    visualize_dataset(
        output,
        specific_image=image,
        save_viz=not no_save,
    )


@app.command()
def audit(
    path: Path = typer.Argument(
        ...,
        help="Path to the dataset directory to audit",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    gate: Path = typer.Option(
        None,
        "--gate",
        "-g",
        help="Path to quality_gate.yaml file",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """
    Audit a generated dataset for quality and integrity.

    Calculates geometric and environmental metrics and checks against quality gates.
    """
    from .data_io.auditor import DatasetAuditor
    from .data_io.auditor_schema import QualityGateConfig
    from rich.table import Table
    import yaml

    console.print(
        Panel.fit(
            "[bold blue]render-tag[/bold blue] Dataset Auditor",
            border_style="blue",
        )
    )

    try:
        # Load gate config if provided
        gate_config = None
        if gate:
            with open(gate) as f:
                gate_data = yaml.safe_load(f)
            gate_config = QualityGateConfig(**gate_data)

        auditor = DatasetAuditor(path)
        result = auditor.run_audit(gate_config=gate_config)
        report = result.report

        console.print(f"[bold]AUDIT REPORT: {path.name}[/bold]")
        console.print("────────────────────────────────────────")
        
        # Determine status based on gates if present, otherwise heuristic score
        if gate:
            status_str = "[bold green]PASSED[/bold green] ✅" if result.gate_passed else "[bold red]FAILED[/bold red] ❌"
        else:
            status_str = "[bold green]PASSED[/bold green] ✅" if report.score > 70 else "[bold red]FAILED[/bold red] ❌"
        
        console.print(f"Status:   {status_str}")
        console.print(f"Score:    [bold]{report.score:.1f}/100[/bold]")
        console.print(f"Tags:     {report.geometric.tag_count}")
        console.print(f"Images:   {report.geometric.image_count}")
        console.print("")

        if gate and not result.gate_passed:
            console.print("[bold red]Gate Failures:[/bold red]")
            for failure in result.gate_failures:
                console.print(f"  - {failure}")
            console.print("")

        # Geometric Table
        geom_table = Table(title="Geometric Distributions", box=None)
        geom_table.add_column("Metric", style="cyan")
        geom_table.add_column("Min", justify="right")
        geom_table.add_column("Max", justify="right")
        geom_table.add_column("Mean", justify="right")
        geom_table.add_column("Std", justify="right")

        g = report.geometric
        geom_table.add_row(
            "Distance (m)", 
            f"{g.distance.min:.2f}", f"{g.distance.max:.2f}", 
            f"{g.distance.mean:.2f}", f"{g.distance.std:.2f}"
        )
        geom_table.add_row(
            "Angle (deg)", 
            f"{g.incidence_angle.min:.1f}", f"{g.incidence_angle.max:.1f}", 
            f"{g.incidence_angle.mean:.1f}", f"{g.incidence_angle.std:.1f}"
        )
        console.print(geom_table)

        # Environmental
        env_table = Table(title="Environmental Variance", box=None)
        env_table.add_column("Metric", style="cyan")
        env_table.add_column("Min", justify="right")
        env_table.add_column("Max", justify="right")
        env_table.add_column("Mean", justify="right")

        e = report.environmental
        env_table.add_row(
            "Lighting Int.", 
            f"{e.lighting_intensity.min:.1f}", f"{e.lighting_intensity.max:.1f}", 
            f"{e.lighting_intensity.mean:.1f}"
        )
        console.print(env_table)

        # Integrity
        if report.integrity.impossible_poses > 0:
            console.print(f"[bold red]⚠ Found {report.integrity.impossible_poses} impossible poses (distance < 0)[/bold red]")

        # Exit with error if gate failed
        if gate and not result.gate_passed:
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@app.command()
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
    from .tools.validator import validate_recipe_file

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


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
