"""
CLI Orchestrator for render-tag synthetic data generation.

This module runs in the standard system Python environment and manages
the BlenderProc subprocess for rendering.
"""

import concurrent.futures
import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import typer
from PIL import Image, ImageDraw
from rich.console import Console
from rich.panel import Panel

from .config import GenConfig, load_config
from .generator import Generator

app = typer.Typer(
    name="render-tag",
    help="3D Procedural Synthetic Data Generation for Fiducial Markers",
    add_completion=False,
)
console = Console()


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

    # Check for blenderproc installation
    if not check_blenderproc_installed():
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
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid config: {e}")
        raise typer.Exit(code=1) from None

    # Override num_scenes if provided
    # Create a modified config with the CLI-provided num_scenes
    config_dict = gen_config.model_dump()
    config_dict["dataset"]["num_scenes"] = num_scenes
    gen_config = GenConfig.model_validate(config_dict)

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

    # --- STRATEGY SELECTION ---

    # 1. Resolve Shard Index (Cloud Auto-detect)
    if shard_index == -1 and total_shards > 1:
        shard_index = _resolve_shard_index()
        if shard_index == -1:
            # Fallback if detection failed but user asked for shards
            # (This might happen if default is -1 but total_shards > 1 and NOT in cloud)
            # But if workers > 1, we are in Local Manager Mode, so index -1 is fine there.
            pass

    # 2. Local Parallel (Manager Mode)
    if workers > 1 and total_shards == 1:
        console.print(f"[bold]Running Local Parallel Manager ({workers} workers)[/bold]")
        _run_local_parallel(
            config_path=config,
            output_dir=output,
            num_scenes=num_scenes,
            workers=workers,
            renderer_mode=renderer_mode,
            verbose=verbose,
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
        total_scenes=num_scenes, shard_index=shard_index, total_shards=total_shards
    )

    if not recipes:
        console.print("[yellow]Empty shard range. Exiting.[/yellow]")
        return

    # Unique recipe filename for this shard
    recipe_filename = f"recipes_shard_{shard_index}.json"
    recipe_path = output / recipe_filename
    generator.save_recipe_json(recipes, recipe_filename)
    console.print(f"[dim]Recipe saved to:[/dim] {recipe_path}")

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

    cmd = [
        "blenderproc",
        "run",
        str(script_path),
        "--recipe",
        str(recipe_path),
        "--output",
        str(output),
        "--renderer-mode",
        renderer_mode,
        "--shard-id",
        str(shard_index),
    ]

    console.print("\n[bold]Launching BlenderProc...[/bold]")
    console.print(f"[dim]Command:[/dim] {' '.join(cmd)}\n")

    try:
        # Run BlenderProc subprocess
        result = subprocess.run(
            cmd,
            check=False,  # Handle exit code ourselves
            capture_output=not verbose,
            text=True,
        )

        if result.returncode != 0:
            console.print(f"[bold red]Rendering Failed![/bold red] Exit code: {result.returncode}")
            if result.stderr:
                console.print(f"[red]Error output:[/red]\n{result.stderr[:1000]}")
            raise typer.Exit(code=result.returncode)

        console.print("\n[bold green]✓ Dataset generated successfully![/bold green]")
        console.print(f"[dim]Output saved to:[/dim] {output}")

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


def _resolve_shard_index() -> int:
    """Auto-detect shard index from common Cloud environments."""
    # AWS Batch
    if "AWS_BATCH_JOB_ARRAY_INDEX" in os.environ:
        return int(os.environ["AWS_BATCH_JOB_ARRAY_INDEX"])

    # GCP Cloud Run (Task Index)
    if "CLOUD_RUN_TASK_INDEX" in os.environ:
        return int(os.environ["CLOUD_RUN_TASK_INDEX"])

    # Kubernetes (Job Completion Index)
    if "JOB_COMPLETION_INDEX" in os.environ:
        return int(os.environ["JOB_COMPLETION_INDEX"])

    return -1


def _run_local_parallel(
    config_path: Path,
    output_dir: Path,
    num_scenes: int,
    workers: int,
    renderer_mode: str,
    verbose: bool,
):
    """Spawns multiple instances of 'render-tag generate' recursively."""
    # We call ourselves recursively, but setting total-shards = workers
    # and NO workers flag (so it enters Worker Mode)

    cmd_base = [
        "render-tag",
        "generate",
        "--config",
        str(config_path),
        "--output",
        str(output_dir),
        "--scenes",
        str(num_scenes),
        "--renderer-mode",
        renderer_mode,
        "--total-shards",
        str(workers),  # Split work exactly by worker count
    ]
    if verbose:
        cmd_base.append("--verbose")

    start_time = time.time()

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = []
        for i in range(workers):
            # Recursive call sending specific shard index
            cmd = cmd_base + ["--shard-index", str(i)]
            futures.append(executor.submit(subprocess.run, cmd, check=True))

        # Wait for all
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                future.result()
            except Exception as e:
                console.print(f"[bold red]Worker failed:[/bold red] {e}")
                raise typer.Exit(1)

    elapsed = time.time() - start_time
    console.print(f"[bold green]Parallel execution finished in {elapsed:.2f}s[/bold green]")

    # Merge Results
    _merge_csv_results(output_dir)


def _merge_csv_results(output_dir: Path):
    """Combine tags_shard_*.csv into tags.csv"""
    console.print("Merging worker results...")
    shards = list(output_dir.glob("tags_shard_*.csv"))
    if not shards:
        return

    # Sort to ensure some deterministic order (though rows might be mixed if we just cat)
    # Actually, we should probably sort by filename to keep index order
    shards.sort(key=lambda p: p.name)

    final_csv = output_dir / "tags.csv"
    header_written = False

    with open(final_csv, "w") as outfile:
        for shard_file in shards:
            with open(shard_file) as infile:
                header = infile.readline()
                if not header_written:
                    outfile.write(header)
                    header_written = True
                # Write the rest
                for line in infile:
                    outfile.write(line)
            # Cleanup
            shard_file.unlink()

    console.print(f"[dim]Merged {len(shards)} shards into[/dim] {final_csv}")


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

    from render_tag.experiment import (
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


def _visualize_dataset(
    output_dir: Path,
    specific_image: Any = None,
    save_viz: bool = True,
) -> None:
    """Internal helper to visualize dataset detections."""
    csv_path = output_dir / "tags.csv"
    images_dir = output_dir / "images"
    viz_dir = output_dir / "visualizations"

    if not csv_path.exists():
        console.print(f"[bold red]Error:[/bold red] CSV file not found: {csv_path}")
        return

    # Load detections
    detections: dict[str, list[dict]] = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_id = row["image_id"]
            if img_id not in detections:
                detections[img_id] = []
            detections[img_id].append(
                {
                    "tag_id": int(row["tag_id"]),
                    "corners": [
                        (float(row["x1"]), float(row["y1"])),
                        (float(row["x2"]), float(row["y2"])),
                        (float(row["x3"]), float(row["y3"])),
                        (float(row["x4"]), float(row["y4"])),
                    ],
                }
            )

    if save_viz:
        viz_dir.mkdir(parents=True, exist_ok=True)

    image_ids = (
        [specific_image]
        if specific_image and specific_image in detections
        else list(detections.keys())
    )

    for image_id in image_ids:
        img_path = images_dir / f"{image_id}.png"
        if not img_path.exists():
            continue

        img = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        for det in detections[image_id]:
            corners = det["corners"]
            # Draw polygon
            for i in range(4):
                draw.line([corners[i], corners[(i + 1) % 4]], fill="lime", width=2)
            # Draw BL (red) and other corners
            draw.ellipse(
                [
                    corners[0][0] - 4,
                    corners[0][1] - 4,
                    corners[0][0] + 4,
                    corners[0][1] + 4,
                ],
                fill="red",
            )

        if save_viz:
            out_path = viz_dir / f"{image_id}_viz.png"
            img.save(out_path)
            console.print(f"[dim]Saved visualization:[/dim] {out_path.name}")

        if specific_image:
            img.show()


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
    from .tools.viz_2d import visualize_recipe

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
    _visualize_dataset(
        output,
        specific_image=image,
        save_viz=not no_save,
    )


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
