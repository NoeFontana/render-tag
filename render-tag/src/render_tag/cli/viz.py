"""
Visualization commands.
"""

import subprocess
from pathlib import Path

import typer

from render_tag.config import TagFamily
from render_tag.data_io.visualization import visualize_dataset, visualize_recipe

from .tools import check_blenderproc_installed, console

app = typer.Typer(help="Visualization tools.")


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
    visualize_dataset(
        output,
        specific_image=image,
        save_viz=not no_save,
    )


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
