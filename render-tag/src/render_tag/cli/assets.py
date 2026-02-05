"""
Asset management commands.
"""

import typer

from .tools import console, get_asset_manager

app = typer.Typer(help="Manage binary assets (HDRIs, Textures, etc.)")


@app.command()
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


@app.command()
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
