import hashlib
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from render_tag.cli.tools import console
from render_tag.orchestration.assets import AssetManager
from render_tag.schema.job import JobSpec, get_env_fingerprint

app = typer.Typer(help="Manage and lock rendering jobs.")

def lock(
    config: Annotated[Path, typer.Option("--config", "-c", help="Path to the experiment YAML config.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Where to save the job.json.")] = Path("job.json"),
    assets_dir: Annotated[Path, typer.Option("--assets", help="Local assets directory.")] = Path("assets"),
    seed: Annotated[int, typer.Option("--seed", help="Global seed for this job.")] = 42,
    shard_index: Annotated[int, typer.Option("--shard-index", help="Index of this shard.")] = 0,
    shard_size: Annotated[int, typer.Option("--shard-size", help="Number of scenes in this shard.")] = 10,
):
    """Generate an immutable job.json for a given configuration."""
    console.print(f"[bold blue]Locking job...[/bold blue]")
    
    # 1. Environment Fingerprint
    env_hash, blender_ver = get_env_fingerprint()
    
    # 2. Assets Fingerprint
    am = AssetManager(local_dir=assets_dir)
    assets_hash = am.get_assets_hash()
    
    # 3. Config Fingerprint
    if not config.exists():
        console.print(f"[bold red]Error:[/bold red] Config file {config} not found.")
        raise typer.Exit(code=1)
        
    with open(config, "rb") as f:
        config_hash = hashlib.sha256(f.read()).hexdigest()
        
    # 4. Create Job Spec
    spec = JobSpec(
        env_hash=env_hash,
        blender_version=blender_ver,
        assets_hash=assets_hash,
        config_hash=config_hash,
        seed=seed,
        shard_index=shard_index,
        shard_size=shard_size
    )
    
    # 5. Save to disk
    with open(output, "w") as f:
        f.write(spec.model_dump_json(indent=2))
        
    job_id_short = hashlib.sha256(spec.model_dump_json().encode()).hexdigest()[:12]
    
    console.print(Panel(
        f"Job locked successfully!\n"
        f"[bold cyan]Output:[/bold cyan] {output}\n"
        f"[bold cyan]Job ID:[/bold cyan] [green]{job_id_short}[/green]",
        title="Success",
        border_style="green"
    ))

if __name__ == "__main__":
    app.command()(lock)