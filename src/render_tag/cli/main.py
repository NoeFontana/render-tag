"""
CLI Entry Point.
"""

import subprocess
import sys

import typer
from rich.panel import Panel

from ..common.logging import setup_logging
from . import assets, audit, experiment, generate, job, viz
from .tools import console

app = typer.Typer(
    name="render-tag",
    help="3D Procedural Synthetic Data Generation for Fiducial Markers",
    add_completion=False,
)

# Register sub-apps
app.add_typer(assets.app, name="assets")
app.add_typer(audit.app, name="audit")
app.add_typer(experiment.app, name="experiment")
app.add_typer(viz.app, name="viz")
app.add_typer(job.app, name="job")

# Register top-level commands from generate.py
app.command(name="generate")(generate.run)
app.command(name="validate-config")(generate.validate_config)
app.command(name="validate-recipe")(generate.validate_recipe)

# Register top-level commands from job.py
app.command(name="lock")(job.lock)

# Register top-level commands from viz.py (shortcuts)
app.command(name="info")(viz.info)


@app.command(name="lint-arch")
def lint_arch() -> None:
    """Run architectural linter to enforce Host/Backend isolation."""
    console.print("[bold green]Running architectural linter...[/bold green]")
    try:
        # We use 'lint-imports' command from import-linter
        result = subprocess.run(
            ["lint-imports"],
            capture_output=False,
            check=False,
        )
        if result.returncode != 0:
            console.print("[bold red]Architectural violations detected![/bold red]")
            sys.exit(result.returncode)
        console.print("[bold green]Architectural integrity verified.[/bold green]")
    except FileNotFoundError:
        console.print("[bold red]Error: 'import-linter' not found. Is it installed?[/bold red]")
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    setup_logging()
    console.print(
        Panel.fit(
            "[bold blue]render-tag[/bold blue] Synthetic Data Generator",
            border_style="blue",
        )
    )
    app()


if __name__ == "__main__":
    main()
