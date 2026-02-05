"""
Orchestration logic for sharding and parallel execution in render-tag.
"""

import concurrent.futures
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Set

from rich.console import Console

from ..common.math import SeedManager
from ..config import load_config

console = Console()

# Global list to track active subprocesses for signal handling cleanup
_active_processes: List[subprocess.Popen] = []


def _signal_handler(sig, frame):
    """Handle termination signals by killing all active worker processes."""
    console.print(f"\n[bold red]Received signal {sig}. Terminating workers...[/bold red]")
    for p in _active_processes:
        if p.poll() is None:
            try:
                # On Windows, we might need a different approach, but sticking to Unix-like for now
                p.terminate()
            except Exception:
                pass
    
    # Wait a moment for graceful termination
    time.sleep(0.5)
    for p in _active_processes:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
    
    console.print("[dim]Workers cleaned up. Exiting.[/dim]")
    sys.exit(1)


def get_completed_scene_ids(output_dir: Path) -> Set[int]:
    """
    Identify completed scene IDs by scanning for sidecar JSON files.
    
    Assumes sidecar files follow the pattern 'scene_{id}_meta.json' or 'scene_{id}_cam_{cid}_meta.json'.
    """
    completed_ids = set()
    images_dir = output_dir / "images"
    if not images_dir.exists():
        return completed_ids

    # Regex to match scene_XXXX_meta.json or scene_XXXX_cam_YYYY_meta.json
    pattern = re.compile(r"scene_(\d+)(?:_cam_\d+)?_meta\.json")

    for f in images_dir.glob("*.json"):
        match = pattern.match(f.name)
        if match:
            completed_ids.add(int(match.group(1)))

    return completed_ids


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

    try:
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
    except Exception as e:
        console.print(f"[bold red]Failed to merge results:[/bold red] {e}")


def run_local_parallel(
    config_path: Path,
    output_dir: Path,
    num_scenes: int,
    workers: int,
    renderer_mode: str,
    verbose: bool,
    executor_type: str = "local",
    resume: bool = False,
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
        "--executor",
        executor_type,
    ]
    if verbose:
        cmd_base.append("--verbose")
    if resume:
        cmd_base.append("--resume")

    # Install signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Load config to get master seed for deterministic sharding
    try:
        config = load_config(config_path)
        master_seed = config.dataset.seeds.global_seed
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load config for seed manager: {e}[/yellow]")
        master_seed = 42

    start_time = time.time()
    _active_processes.clear()

    try:
        # Launch processes
        for i in range(workers):
            cmd = [*cmd_base, "--shard-index", str(i)]
            # We use Popen instead of ProcessPoolExecutor for more direct control
            # over the subprocess objects and signal handling.
            p = subprocess.Popen(
                cmd,
                stdout=None if verbose else subprocess.DEVNULL,
                stderr=None if verbose else subprocess.DEVNULL,
            )
            _active_processes.append(p)

        # Wait for all
        failed = False
        for p in _active_processes:
            retcode = p.wait()
            if retcode != 0:
                failed = True
                console.print(f"[bold red]Worker (PID {p.pid}) failed with code {retcode}[/bold red]")

        if failed:
            from typer import Exit
            raise Exit(1)

    finally:
        # Final cleanup attempt
        for p in _active_processes:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        _active_processes.clear()

    elapsed = time.time() - start_time
    console.print(f"[bold green]Parallel execution finished in {elapsed:.2f}s[/bold green]")

    # Merge Results
    merge_csv_results(output_dir)
