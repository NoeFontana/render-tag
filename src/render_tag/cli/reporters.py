from pathlib import Path
from typing import Protocol

from rich.console import Console
from rich.table import Table

from render_tag.orchestration.result import OrchestrationResult


class BaseReporter(Protocol):
    """Protocol for orchestration result reporters."""

    def report(self, result: OrchestrationResult) -> None:
        """Present the result to the user or a file."""
        ...


class RichTerminalReporter:
    """Reporter that uses 'rich' to print formatted results to the terminal."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def report(self, result: OrchestrationResult) -> None:
        """Print a rich summary of the orchestration results."""
        self.console.print("\n[bold]Orchestration Summary[/bold]")

        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Metric", style="dim")
        table.add_column("Value")

        table.add_row("Success Count", str(result.success_count))
        table.add_row("Failed Count", str(result.failed_count))
        table.add_row("Skipped Count", str(result.skipped_count))
        table.add_row("Total Duration", f"{result.timings.total_duration_s:.2f}s")

        if result.worker_metrics:
            table.add_row("Max RAM Used", f"{result.worker_metrics.max_ram_mb:.1f} MB")
            table.add_row("Max VRAM Used", f"{result.worker_metrics.max_vram_mb:.1f} MB")

        self.console.print(table)

        if result.errors:
            self.console.print("\n[bold red]Failures:[/bold red]")
            error_table = Table(show_header=True, header_style="bold red")
            error_table.add_column("Scene ID")
            error_table.add_column("Error Message")

            for err in result.errors[:10]:  # Cap at 10 for terminal
                error_table.add_row(str(err.scene_id), err.error_message)

            self.console.print(error_table)
            if len(result.errors) > 10:
                self.console.print(f"... and {len(result.errors) - 10} more errors.")


class JsonFileReporter:
    """Reporter that writes results to a JSON file."""

    def __init__(self, output_path: Path):
        self.output_path = output_path

    def report(self, result: OrchestrationResult) -> None:
        """Save result as JSON."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            f.write(result.model_dump_json(indent=4))
