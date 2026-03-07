"""
Visualization commands.
"""

import subprocess
from pathlib import Path

import typer

from render_tag.core.config import TagFamily

try:
    from render_tag.data_io.visualization import (
        visualize_dataset,
        visualize_fiftyone,
        visualize_recipe,
    )
except ImportError:
    visualize_dataset = None
    visualize_fiftyone = None
    visualize_recipe = None

from .tools import check_blenderproc_installed, check_viz_installed, console

app = typer.Typer(help="Visualization tools.")


def _ensure_viz():
    if not check_viz_installed():
        console.print("[bold red]Error:[/bold red] Visualization dependencies not installed.")
        console.print("Install with: [cyan]pip install 'render-tag[viz]'[/cyan]")
        raise typer.Exit(code=1)


@app.command(name="recipe")
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
    _ensure_viz()

    output.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Visualizing recipe:[/dim] {recipe}")

    try:
        visualize_recipe(recipe, output)
        console.print(f"[bold green]✓ Visualization saved to:[/bold green] {output}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Visualization failed: {e}")
        raise typer.Exit(code=1) from None


@app.command(name="dataset")
def viz_dataset(
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
    _ensure_viz()

    visualize_dataset(
        output,
        specific_image=image,
        save_viz=not no_save,
    )


@app.command(name="fiftyone")
def viz_fiftyone(
    dataset: Path = typer.Option(
        ...,
        "--dataset",
        "-d",
        help="Path to the dataset directory",
        exists=True,
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
    ),
    address: str = typer.Option(
        "0.0.0.0",
        "--address",
        "-a",
        help="Address to host FiftyOne App on",
    ),
    port: int = typer.Option(
        5151,
        "--port",
        "-p",
        help="Port to host FiftyOne App on",
    ),
    remote: bool = typer.Option(
        False,
        "--remote",
        help="Run in headless mode for remote cluster access",
    ),
) -> None:
    """
    Visualize a dataset with Voxel51 FiftyOne.

    Joins COCO annotations with rich truth metadata and launches the FiftyOne App.
    """
    _ensure_viz()

    if visualize_fiftyone is None:
        console.print("[bold red]Error:[/bold red] FiftyOne visualization logic not found.")
        raise typer.Exit(code=1)

    console.print(f"[dim]Launching FiftyOne for dataset:[/dim] {dataset}")

    try:
        visualize_fiftyone(dataset, address=address, port=port, remote=remote)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] FiftyOne failed: {e}")
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
    console.print("\n[bold]Supported Tag Families:[/bold]")
    apriltags = [t for t in TagFamily if t.is_apriltag]
    arucos = [t for t in TagFamily if t.is_aruco]
    console.print(f"  AprilTag: {len(apriltags)} families")
    console.print(f"  ArUco: {len(arucos)} dictionaries")
