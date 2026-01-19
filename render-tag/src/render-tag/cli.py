import typer
import subprocess
from pathlib import Path
from rich.console import Console

app = typer.Typer(help="render-tag: 3D Procedural Engine")
console = Console()

@app.command()
def generate(
    config: Path = typer.Option("configs/default.yaml", help="Generation config"),
    output: Path = typer.Option("output/dataset_01", help="Destination"),
):
    """
    Launch the BlenderProc subprocess to generate the dataset.
    """
    console.print(f"[bold blue]Starting BlenderProc...[/bold blue]")
    
    # We invoke the internal script using the blenderproc executable
    script_path = Path(__file__).parent / "scripts" / "blender_main.py"
    
    cmd = [
        "blenderproc", "run", 
        str(script_path),
        "--config", str(config),
        "--output", str(output)
    ]
    
    subprocess.run(cmd, check=True)
    console.print(f"[bold green]✓ Dataset saved to {output}[/bold green]")

if __name__ == "__main__":
    app()
