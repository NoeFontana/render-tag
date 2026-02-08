"""
Orchestration logic for sharding and parallel execution in render-tag.
"""

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console

from ..common.logging import get_logger
from ..config import load_config

console = Console()
logger = get_logger(__name__)

# Global list to track active subprocesses for signal handling cleanup
_active_processes: list[subprocess.Popen] = []


def _signal_handler(sig, frame):
    """Handle termination signals by killing all active worker processes."""
    console.print(f"\n[bold red]Received signal {sig}. Terminating workers...[/bold red]")
    from .unified_orchestrator import UnifiedWorkerOrchestrator
    UnifiedWorkerOrchestrator.cleanup_all()
    
    console.print("[dim]Workers cleaned up. Exiting.[/dim]")
    sys.exit(1)


def get_completed_scene_ids(output_dir: Path) -> set[int]:
    """
    Identify completed scene IDs by scanning for sidecar JSON files.

    Assumes sidecar files follow the pattern 'scene_{id}_meta.json' 
    or 'scene_{id}_cam_{cid}_meta.json'.
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
    """Combine tags_shard_*.csv into tags.csv, preserving existing results."""
    logger.info("Merging worker results...")
    shards = list(output_dir.glob("tags_shard_*.csv"))
    if not shards:
        return

    # Sort to ensure some deterministic order
    shards.sort(key=lambda p: p.name)

    final_csv = output_dir / "tags.csv"
    
    # If final_csv exists, we append to it (skipping headers in shards)
    # If it doesn't, we create it and write the header from the first shard.
    exists = final_csv.exists()
    header_written = exists

    try:
        mode = "a" if exists else "w"
        with open(final_csv, mode) as outfile:
            for shard_file in shards:
                with open(shard_file) as infile:
                    header = infile.readline()
                    if not header_written:
                        outfile.write(header)
                        header_written = True
                    # Write the rest
                    for line in infile:
                        outfile.write(line)
                # Cleanup shard file after successful merge
                shard_file.unlink()
        console.print(f"[dim]Merged {len(shards)} new shards into[/dim] {final_csv}")
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
    batch_size: int = 10,
):
    """
    Executes renders in parallel using a dynamic task pool (Batch Stealing).
    
    1. Generates all required scene recipes.
    2. Groups recipes into batches.
    3. Spawns workers that pull and execute batches until the pool is empty.
    """
    from ..generator import Generator
    from .executors import ExecutorFactory

    # 1. Setup
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    _active_processes.clear()

    # 2. Identify completed scenes if resuming
    completed_ids = set()
    if resume:
        completed_ids = get_completed_scene_ids(output_dir)

    # 3. Generate ALL missing recipes
    try:
        config = load_config(config_path)
    except Exception as e:
        console.print(f"[bold red]Failed to load config:[/bold red] {e}")
        from typer import Exit
        raise Exit(1) from None

    # Override num_scenes from CLI argument
    config.dataset.num_scenes = num_scenes

    generator = Generator(config, output_dir)
    all_recipes = generator.generate_all(exclude_ids=completed_ids)
    
    if not all_recipes:
        console.print("[yellow]No new scenes to generate. All tasks complete.[/yellow]")
        return

    console.print(
        f"[bold]Orchestrating {len(all_recipes)} scenes across {workers} workers "
        f"(Batch size: {batch_size})[/bold]"
    )

    # 4. Group into batches
    batches = []
    for i in range(0, len(all_recipes), batch_size):
        batch = all_recipes[i : i + batch_size]
        batch_id = i // batch_size
        recipe_filename = f"recipes_batch_{batch_id}.json"
        recipe_path = generator.save_recipe_json(batch, recipe_filename)
        batches.append((batch_id, recipe_path))

    start_time = time.time()
    
    # 5. Execute batches using a simple work-queue model
    # We'll use a local executor for each worker
    executor = ExecutorFactory.get_executor(executor_type)
    
    from queue import Queue
    from threading import Thread

    task_queue = Queue()
    for b in batches:
        task_queue.put(b)

    results = []

    def worker_thread(worker_id):
        while not task_queue.empty():
            try:
                batch_id, recipe_path = task_queue.get_nowait()
            except Exception:
                break

            logger.info(f"Worker {worker_id} pulling batch {batch_id}...")
            
            # For subprocess management, we still want to track PIDs
            # But the executor currently uses subprocess.run (blocking)
            # We need to monkey-patch or refactor executor to use Popen 
            # if we want SIGINT to work perfectly
            # Actually, since we are in a thread, subprocess.run is fine 
            # as long as we can kill the whole group
            try:
                # We need a way to track the subprocess inside the executor
                # For now, let's keep it simple and assume SIGINT hits the whole process group
                executor.execute(
                    recipe_path=recipe_path,
                    output_dir=output_dir,
                    renderer_mode=renderer_mode,
                    shard_id=f"batch_{batch_id}",
                    verbose=verbose
                )
                results.append((batch_id, True))
            except Exception as e:
                console.print(f"[bold red]Batch {batch_id} failed:[/bold red] {e}")
                results.append((batch_id, False))
            finally:
                task_queue.task_done()

    threads = []
    for i in range(workers):
        t = Thread(target=worker_thread, args=(i,), daemon=True)
        t.start()
        threads.append(t)

    # Wait for all batches to finish
    for t in threads:
        t.join()

    elapsed = time.time() - start_time
    failed_batches = [bid for bid, success in results if not success]
    
    if failed_batches:
        console.print(
            f"[bold red]Parallel execution finished with {len(failed_batches)} "
            "failed batches.[/bold red]"
        )
        from typer import Exit
        raise Exit(1) from None
    
    logger.info(f"Parallel execution finished in {elapsed:.2f}s")

    # 6. Cleanup batch files
    for _, recipe_path in batches:
        if recipe_path.exists():
            recipe_path.unlink()

    # Merge Results
    merge_csv_results(output_dir)
