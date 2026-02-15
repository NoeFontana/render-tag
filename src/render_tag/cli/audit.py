"""
Dataset auditing commands.
"""

import json
from pathlib import Path

import typer
import yaml
from rich.table import Table

from render_tag.audit.auditor import (
    AuditDiff,
    AuditResult,
    DatasetAuditor,
    DatasetReader,
    QualityGateConfig,
)
from render_tag.audit.reporting import DashboardGenerator

from .tools import check_audit_installed, console

app = typer.Typer(help="Audit and compare datasets.")


def _ensure_audit():
    if not check_audit_installed():
        console.print("[bold red]Error:[/bold red] Auditing dependencies not installed.")
        console.print("Install with: [cyan]pip install 'render-tag[audit]'[/cyan]")
        raise typer.Exit(code=1)


@app.command(name="run")
def run(
    path: Path = typer.Argument(
        ...,
        help="Path to the dataset directory to audit",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    gate: Path = typer.Option(
        None,
        "--gate",
        "-g",
        help="Path to quality_gate.yaml file",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """
    Audit a generated dataset for quality and integrity.
    """
    _ensure_audit()

    try:
        # Load gate config if provided
        gate_config = None
        if gate:
            with open(gate) as f:
                gate_data = yaml.safe_load(f)
            gate_config = QualityGateConfig(**gate_data)

        auditor = DatasetAuditor(path)
        result = auditor.run_audit(gate_config=gate_config)
        report = result.report

        # Save JSON Report
        report_path = path / "audit_report.json"
        with open(report_path, "w") as f:
            f.write(result.model_dump_json(indent=2))
        console.print(f"[dim]Audit report saved to:[/dim] {report_path}")

        # Generate Dashboard
        viz_path = DashboardGenerator(path, result).generate()
        console.print(f"[dim]Audit dashboard saved to:[/dim] {viz_path}")

        console.print(f"[bold]AUDIT REPORT: {path.name}[/bold]")
        console.print("────────────────────────────────────────")

        # Determine status based on gates if present, otherwise heuristic score
        is_passed = result.gate_passed if gate else report.score > 70
        if is_passed:
            status_str = "[bold green]PASSED[/bold green] ✅"
        else:
            status_str = "[bold red]FAILED[/bold red] ❌"

        console.print(f"Status:   {status_str}")
        console.print(f"Score:    [bold]{report.score:.1f}/100[/bold]")
        console.print(f"Tags:     {report.geometric.tag_count}")
        console.print(f"Images:   {report.geometric.image_count}")
        console.print("")

        if gate and not result.gate_passed:
            console.print("[bold red]Gate Failures:[/bold red]")
            for failure in result.gate_failures:
                console.print(f"  - {failure}")
            console.print("")

        # Geometric Table
        geom_table = Table(title="Geometric Distributions", box=None)
        geom_table.add_column("Metric", style="cyan")
        geom_table.add_column("Min", justify="right")
        geom_table.add_column("Max", justify="right")
        geom_table.add_column("Mean", justify="right")
        geom_table.add_column("Std", justify="right")

        g = report.geometric
        geom_table.add_row(
            "Distance (m)",
            f"{g.distance.min:.2f}",
            f"{g.distance.max:.2f}",
            f"{g.distance.mean:.2f}",
            f"{g.distance.std:.2f}",
        )
        geom_table.add_row(
            "Angle (deg)",
            f"{g.incidence_angle.min:.1f}",
            f"{g.incidence_angle.max:.1f}",
            f"{g.incidence_angle.mean:.1f}",
            f"{g.incidence_angle.std:.1f}",
        )
        if g.ppm:
            geom_table.add_row(
                "PPM",
                f"{g.ppm.min:.1f}",
                f"{g.ppm.max:.1f}",
                f"{g.ppm.mean:.1f}",
                f"{g.ppm.std:.1f}",
            )
        console.print(geom_table)

        # Environmental
        env_table = Table(title="Environmental Variance", box=None)
        env_table.add_column("Metric", style="cyan")
        env_table.add_column("Min", justify="right")
        env_table.add_column("Max", justify="right")
        env_table.add_column("Mean", justify="right")

        e = report.environmental
        env_table.add_row(
            "Lighting Int.",
            f"{e.lighting_intensity.min:.1f}",
            f"{e.lighting_intensity.max:.1f}",
            f"{e.lighting_intensity.mean:.1f}",
        )
        console.print(env_table)

        # Integrity
        if report.integrity.impossible_poses > 0:
            msg = (
                f"[bold red]⚠ Found {report.integrity.impossible_poses} impossible poses[/bold red]"
            )
            console.print(msg)

        # Exit with error if gate failed
        if gate and not result.gate_passed:
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@app.command(name="diff")
def diff(
    path_a: Path = typer.Argument(..., help="Path to the first (baseline) dataset"),
    path_b: Path = typer.Argument(..., help="Path to the second (new) dataset"),
) -> None:
    """
    Compare two datasets and detect statistical drift.
    """
    _ensure_audit()

    try:
        # Load reports
        reports = []
        for p in [path_a, path_b]:
            report_file = p / "audit_report.json"
            if not report_file.exists():
                console.print(f"[dim]Generating audit for {p.name}...[/dim]")
                auditor = DatasetAuditor(p)
                res = auditor.run_audit()
                reports.append(res.report)
            else:
                with open(report_file) as f:
                    res_data = json.load(f)
                reports.append(AuditResult(**res_data).report)

        # Calculate Diff
        diff_calc = AuditDiff(reports[0], reports[1])
        deltas = diff_calc.calculate()

        # Display results
        console.print(f"Comparing [cyan]{path_a.name}[/cyan] vs [cyan]{path_b.name}[/cyan]")
        console.print("────────────────────────────────────────")

        diff_table = Table(title="Statistical Drift (B - A)", box=None)
        diff_table.add_column("Metric", style="cyan")
        diff_table.add_column("Delta", justify="right")

        def fmt_delta(val, inverse=False):
            color = "green" if (val >= 0 if not inverse else val <= 0) else "red"
            prefix = "+" if val >= 0 else ""
            return f"[{color}]{prefix}{val:.2f}[/{color}]"

        diff_table.add_row("Tag Count", fmt_delta(deltas["tag_count"]))
        diff_table.add_row("Image Count", fmt_delta(deltas["image_count"]))
        diff_table.add_row("Distance Mean", fmt_delta(deltas["distance_mean_diff"]))
        diff_table.add_row("Max Angle", fmt_delta(deltas["incidence_angle_max_diff"]))
        diff_table.add_row(
            "Impossible Poses", fmt_delta(deltas["impossible_poses_diff"], inverse=True)
        )
        diff_table.add_row("Quality Score", fmt_delta(deltas["score_diff"]))

        console.print(diff_table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@app.command(name="prune")
def prune(
    path: Path = typer.Argument(
        ...,
        help="Path to the dataset directory to prune",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    limit: int = typer.Option(200, "--limit", "-l", help="Target number of images"),
    min_dist: float = typer.Option(None, "--min-dist", help="Min distance"),
    max_dist: float = typer.Option(None, "--max-dist", help="Max distance"),
    max_occlusion: float = typer.Option(0.1, "--max-occlusion", help="Max occlusion ratio"),
    max_angle: float = typer.Option(80.0, "--max-angle", help="Max incidence angle"),
) -> None:
    """
    Prune invalid/low-quality samples and truncate to a fixed size.
    """
    _ensure_audit()
    import polars as pl

    try:
        reader = DatasetReader(path)
        df = reader.load_rich_detections()
        initial_count = df["image_id"].n_unique()

        # Apply Filters
        mask = pl.col("occlusion_ratio") <= max_occlusion
        mask = mask & (pl.col("angle_of_incidence") <= max_angle)

        if min_dist is not None:
            mask = mask & (pl.col("distance") >= min_dist)
        if max_dist is not None:
            mask = mask & (pl.col("distance") <= max_dist)

        filtered_df = df.filter(mask)

        # Get unique valid images
        valid_images = filtered_df["image_id"].unique().to_list()

        # Diversify selection (shuffle)
        import random

        random.seed(42)
        random.shuffle(valid_images)

        # Truncate
        selected_images = valid_images[:limit]
        final_count = len(selected_images)

        if final_count < limit:
            console.print(
                f"[yellow]Warning: Only {final_count} images passed filters "
                f"(limit {limit})[/yellow]"
            )

        # Update Files (tags.csv, rich_truth.json)
        # Note: In a real scenario we might delete the actual images too
        # but for this CLI tool we focus on updating metadata.

        selected_set = set(selected_images)

        # Update rich_truth.json
        rich_path = path / "rich_truth.json"
        if rich_path.exists():
            with open(rich_path) as f:
                rich_data = json.load(f)
            new_rich = [d for d in rich_data if d["image_id"] in selected_set]
            with open(rich_path, "w") as f:
                json.dump(new_rich, f, indent=2)

        # Update tags.csv
        tags_path = path / "tags.csv"
        if tags_path.exists():
            tags_df = pl.read_csv(tags_path)
            new_tags_df = tags_df.filter(pl.col("image_id").is_in(selected_images))
            new_tags_df.write_csv(tags_path)

        console.print("[bold green]Pruning Complete[/bold green]")
        console.print(f"  Initial: {initial_count} images")
        console.print(f"  Final:   {final_count} images")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@app.command(name="logs")
def logs(
    path: Path = typer.Option(..., "--path", "-p", help="Path to log file (JSONL)", exists=True),
    level: str = typer.Option(
        None, "--level", "-l", help="Filter by log level (INFO, WARNING, ERROR)"
    ),
    query: str = typer.Option(
        None,
        "--query",
        "-q",
        help="Python expression to filter logs (e.g. 'context[\"scene_id\"] == 5')",
    ),
    limit: int = typer.Option(100, "--limit", "-n", help="Max number of logs to show"),
) -> None:
    """
    Query and filter structured JSON logs.
    """
    import orjson
    from rich.syntax import Syntax

    console.print(f"[bold]Querying Logs:[/bold] {path}")
    if level:
        console.print(f"  Filter: Level={level.upper()}")
    if query:
        console.print(f"  Filter: Query='{query}'")
    console.print("────────────────────────────────────────")

    count = 0
    try:
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                # Filter by level
                if level and record.get("level", "").upper() != level.upper():
                    continue

                # Filter by query
                if query:
                    try:
                        # Construct evaluation context
                        # Allow direct access to top-level keys, context keys, and payload keys
                        eval_ctx = {
                            "record": record,
                            "context": record.get("context", {}),
                            "payload": record.get("payload", {}),
                        }
                        # Merge flattened view for convenience
                        eval_ctx.update(record)
                        eval_ctx.update(record.get("context", {}))
                        eval_ctx.update(record.get("payload", {}))

                        if not eval(query, {}, eval_ctx):
                            continue
                    except Exception:
                        # If query fails (e.g. missing key), safely skip
                        continue

                # Pretty print result
                # We format it back to JSON for syntax highlighting
                formatted_json = orjson.dumps(record, option=orjson.OPT_INDENT_2).decode("utf-8")
                console.print(Syntax(formatted_json, "json", theme="monokai", word_wrap=True))

                count += 1
                if count >= limit:
                    console.print(
                        f"\n[yellow]Limit reached ({limit}). Use --limit to see more.[/yellow]"
                    )
                    break

        if count == 0:
            console.print("[yellow]No logs matched criteria.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error reading logs:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@app.command(name="recipes")
def audit_recipes(
    path: Path = typer.Argument(
        ..., help="Path to scene_recipes.json", exists=True, dir_okay=False
    ),
) -> None:
    """
    Audit scene recipes for statistical distributions before rendering.
    """
    from render_tag.audit.recipe_auditor import RecipeAuditor
    from render_tag.core.schema import SceneRecipe

    console.print(f"[dim]Auditing recipes in:[/dim] {path}")
    try:
        with open(path) as f:
            data = json.load(f)

        recipes_data = data if isinstance(data, list) else [data]
        recipes = [SceneRecipe.model_validate(item) for item in recipes_data]

        auditor = RecipeAuditor(recipes)
        report = auditor.run_audit()

        console.print(auditor.render_table(report))
        console.print(f"Total Scenes: {report.scene_count}")
        console.print(f"Total Cameras: {report.camera_count}")
        console.print(f"Total Tags:    {report.tag_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from None
