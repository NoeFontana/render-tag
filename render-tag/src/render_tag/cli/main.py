"""
CLI Entry Point.
"""

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
app.command(name="run")(generate.run)
app.command(name="validate-config")(generate.validate_config)
app.command(name="validate-recipe")(generate.validate_recipe)

# Register top-level commands from job.py
app.command(name="lock")(job.lock)

# Register top-level commands from viz.py (shortcuts)
app.command(name="viz")(viz.viz_dataset)
app.command(name="viz-recipe")(viz.viz_recipe)
app.command(name="info")(viz.info)


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
