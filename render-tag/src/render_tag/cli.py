"""
CLI Orchestrator for render-tag synthetic data generation.

This module runs in the standard system Python environment and manages
the BlenderProc subprocess for rendering.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .config import GenConfig, load_config

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
        "--config", "-c",
        help="Path to the generation config YAML file",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path = typer.Option(
        "output/dataset_01",
        "--output", "-o",
        help="Output directory for generated dataset",
        resolve_path=True,
    ),
    num_scenes: int = typer.Option(
        1,
        "--scenes", "-n",
        help="Number of scenes to generate",
        min=1,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose output from BlenderProc",
    ),
) -> None:
    """
    Generate synthetic fiducial marker training data.
    
    Launches BlenderProc to render scenes with AprilTags/ArUco markers,
    producing images and corner annotations for detector training.
    """
    console.print(Panel.fit(
        "[bold blue]render-tag[/bold blue] Synthetic Data Generator",
        border_style="blue",
    ))
    
    # Check for blenderproc installation
    if not check_blenderproc_installed():
        console.print(
            "[bold red]Error:[/bold red] blenderproc is not installed or not in PATH.\n"
            "Install it with: [cyan]pip install blenderproc[/cyan]"
        )
        raise typer.Exit(code=1)
    
    # Load and validate configuration
    console.print(f"[dim]Loading config from[/dim] {config}")
    try:
        gen_config = load_config(config)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config}")
        raise typer.Exit(code=1)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid config: {e}")
        raise typer.Exit(code=1)
    
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
    console.print(f"[dim]Job config:[/dim] {job_config_path}")
    
    # Pre-generate tag assets if they don't exist
    from .tag_gen import ensure_tag_asset
    from .config import TAG_BIT_COUNTS
    
    assets_dir = Path("assets/tags")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Get families from scenario if present
    scenario = gen_config.scenario
    families = scenario.tag_families if scenario else [gen_config.tag.family]
    
    tags_per_scene = scenario.tags_per_scene[1] if scenario else 1
    
    console.print(f"\n[bold]Ensuring tag assets...[/bold]")
    for family_enum in families:
        family = family_enum.value
        # For simplicity, we ensure a few tags for each family
        # In a more advanced version, we'd use the specific IDs requested
        for i in range(max(tags_per_scene, 10)):
            asset_path = ensure_tag_asset(family, i, assets_dir)
            if verbose:
                console.print(f"  [dim]Checked asset:[/dim] {asset_path.name}")
    
    # Build the blenderproc command
    script_path = Path(__file__).parent / "scripts" / "blender_main.py"
    
    cmd = [
        "blenderproc", "run",
        str(script_path),
        "--config", str(job_config_path),
        "--output", str(output),
    ]
    
    console.print(f"\n[bold]Launching BlenderProc...[/bold]")
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
        
        console.print(f"\n[bold green]✓ Dataset generated successfully![/bold green]")
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
        raise typer.Exit(code=1)
    
    finally:
        # Clean up temporary config file
        if job_config_path.exists():
            job_config_path.unlink()


@app.command()
def validate(
    config: Path = typer.Option(
        "configs/default.yaml",
        "--config", "-c",
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
        console.print(f"\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Resolution: {gen_config.camera.resolution}")
        console.print(f"  FOV: {gen_config.camera.fov}°")
        console.print(f"  Tag Family: {gen_config.tag.family.value}")
        console.print(f"  Tag Size: {gen_config.tag.size_meters}m")
        console.print(f"  Samples/Scene: {gen_config.camera.samples_per_scene}")
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config}")
        raise typer.Exit(code=1)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid config: {e}")
        raise typer.Exit(code=1)


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
    console.print(f"\n[bold]Supported Tag Families:[/bold]")
    apriltags = [t for t in TagFamily if t.is_apriltag]
    arucos = [t for t in TagFamily if t.is_aruco]
    console.print(f"  AprilTag: {len(apriltags)} families")
    console.print(f"  ArUco: {len(arucos)} dictionaries")


@app.command()
def viz(
    output: Path = typer.Option(
        ...,
        "--output", "-o",
        help="Path to the dataset output directory",
        exists=True,
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
    ),
    image: str = typer.Option(
        None,
        "--image", "-i",
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
    
    This tool draws corner markers and quadrilaterals on images
    to verify that annotations align correctly with tag borders.
    """
    from .tools.viz import visualize_dataset
    
    visualize_dataset(
        output,
        specific_image=image,
        save_viz=not no_save,
    )


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

