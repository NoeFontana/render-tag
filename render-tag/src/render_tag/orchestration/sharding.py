"""
Orchestration logic for sharding and parallel execution in render-tag.
"""

import concurrent.futures
import os
import subprocess
import time
from pathlib import Path

from rich.console import Console

from ..common.math import SeedManager
from ..config import load_config

console = Console()


def resolve_shard_index() -> int:
    """Auto-detect shard index from common Cloud environments."""
    # AWS Batch
    if "AWS_BATCH_JOB_ARRAY_INDEX" in os.environ:
        return int(os.environ["AWS_BATCH_JOB_ARRAY_INDEX"])

    # GCP Cloud Run (Task Index)
    if "CLOUD_RUN_TASK_INDEX" in os.environ:
        return int(os.environ["CLOUD_RUN_TASK_INDEX"])

    # Kubernetes (Job Completion Index)
    if "JOB_COMPLETION_INDEX" in os.environ:
        return int(os.environ["JOB_COMPLETION_INDEX"])

    return -1


def merge_csv_results(output_dir: Path):
    """Combine tags_shard_*.csv into tags.csv"""
    console.print("Merging worker results...")
    shards = list(output_dir.glob("tags_shard_*.csv"))
    if not shards:
        return

    # Sort to ensure some deterministic order
    shards.sort(key=lambda p: p.name)

    final_csv = output_dir / "tags.csv"
    header_written = False

    with open(final_csv, "w") as outfile:
        for shard_file in shards:
            with open(shard_file) as infile:
                header = infile.readline()
                if not header_written:
                    outfile.write(header)
                    header_written = True
                # Write the rest
                for line in infile:
                    outfile.write(line)
            # Cleanup
            shard_file.unlink()

    console.print(f"[dim]Merged {len(shards)} shards into[/dim] {final_csv}")


def run_local_parallel(
    config_path: Path,
    output_dir: Path,
    num_scenes: int,
    workers: int,
    renderer_mode: str,
    verbose: bool,
):
    """Spawns multiple instances of 'render-tag generate' recursively."""
    cmd_base = [
        "render-tag",
        "generate",
        "--config",
        str(config_path),
        "--output",
        str(output_dir),
        "--scenes",
        str(num_scenes),
        "--renderer-mode",
        renderer_mode,
        "--total-shards",
        str(workers),  # Split work exactly by worker count
    ]
    if verbose:
        cmd_base.append("--verbose")

    # Load config to get master seed for deterministic sharding
    try:
        config = load_config(config_path)
        master_seed = config.dataset.seeds.global_seed
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load config for seed manager: {e}[/yellow]")
        master_seed = 42

    seed_manager = SeedManager(master_seed)

    start_time = time.time()

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = []
        for i in range(workers):
            shard_seed = seed_manager.get_shard_seed(i)
            # Recursive call sending specific shard index and deterministic seed
            cmd = [*cmd_base, "--shard-index", str(i), "--seed", str(shard_seed)]
            futures.append(executor.submit(subprocess.run, cmd, check=True))

        # Wait for all
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                console.print(f"[bold red]Worker failed:[/bold red] {e}")
                from typer import Exit

                raise Exit(1) from None

    elapsed = time.time() - start_time
    console.print(f"[bold green]Parallel execution finished in {elapsed:.2f}s[/bold green]")

    # Merge Results
    merge_csv_results(output_dir)
