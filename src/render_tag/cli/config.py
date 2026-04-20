"""Config migration commands.

Provides `render-tag config migrate` — a user-facing tool for upgrading legacy
YAML/JSON configs to the current schema via the Anti-Corruption Layer.
"""

from __future__ import annotations

import copy
import difflib
import json
import warnings
from pathlib import Path

import typer
import yaml

from render_tag.cli.tools import console
from render_tag.core.schema_adapter import SchemaMigrator, adapt_config

app = typer.Typer(help="Config inspection and migration utilities.")


def _load(path: Path) -> dict:
    with open(path) as f:
        if path.suffix.lower() in (".yaml", ".yml"):
            return yaml.safe_load(f) or {}
        if path.suffix.lower() == ".json":
            return json.load(f)
    raise typer.BadParameter(f"Unsupported file type: {path.suffix}")


def _dump(path: Path, data: dict) -> str:
    if path.suffix.lower() in (".yaml", ".yml"):
        return yaml.dump(data, sort_keys=False)
    return json.dumps(data, indent=2) + "\n"


@app.command("migrate")
def migrate(
    path: Path = typer.Argument(
        ..., help="Path to legacy config YAML/JSON", exists=True, resolve_path=True
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Rewrite the file in place (default: dry-run, print unified diff to stdout).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write upgraded config to this path instead of --write/stdout.",
        resolve_path=True,
    ),
) -> None:
    """Upgrade a legacy config to the current schema.

    By default, prints a unified diff to stdout. Use --write to rewrite the file
    in place, or --output PATH to write to a new file.
    """
    original = _load(path)
    migrator = SchemaMigrator()
    original_version = migrator.get_version(original)

    # Deepcopy so adapt_config's in-place mutations of nested dicts don't also
    # mutate `original` (which we compare against for the diff).
    # Silence deprecation warnings during migration — the user is explicitly
    # running the migration tool; the warnings would just be noise on top of
    # the diff output.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        upgraded = adapt_config(copy.deepcopy(original))

    upgraded_text = _dump(path, upgraded)

    if original == upgraded:
        console.print(f"[green]{path}[/green] is already at schema v{migrator.target_version}.")
        return

    if output is not None:
        output.write_text(upgraded_text)
        console.print(
            f"[green]Wrote upgraded config to[/green] {output} "
            f"(v{original_version} -> v{migrator.target_version})"
        )
        return

    if write:
        path.write_text(upgraded_text)
        console.print(
            f"[green]Upgraded[/green] {path} (v{original_version} -> v{migrator.target_version})"
        )
        return

    # Dry-run: print diff
    original_text = _dump(path, original)
    diff = difflib.unified_diff(
        original_text.splitlines(keepends=True),
        upgraded_text.splitlines(keepends=True),
        fromfile=f"{path} (v{original_version})",
        tofile=f"{path} (v{migrator.target_version})",
    )
    diff_output = "".join(diff)
    if diff_output:
        console.print(diff_output, markup=False, highlight=False, end="")
        console.print(
            "\n[dim]Run with --write to apply these changes in place, "
            "or --output PATH to write to a new file.[/dim]"
        )
    else:
        console.print(f"[green]{path}[/green] is already at schema v{migrator.target_version}.")
