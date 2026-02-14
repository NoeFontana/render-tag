"""
Dataset auditing commands.
"""

import json
from pathlib import Path

import typer
import yaml
from rich.table import Table

try:
    from render_tag.audit.auditor import AuditDiff, DatasetAuditor
    from render_tag.audit.auditor import AuditResult, QualityGateConfig
    from render_tag.audit.reporting import DashboardGenerator
except ImportError:
    AuditDiff = None
    DatasetAuditor = None
    AuditResult = None
    QualityGateConfig = None
    DashboardGenerator = None

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
