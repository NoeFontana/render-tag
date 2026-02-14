"""
Orchestration utilities for sharding, parallel execution, and worker management.
"""

import hashlib
import json
import logging
import os
import queue
import re
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, ClassVar

from rich.console import Console

try:
    import zmq
except ImportError:
    zmq = None

from render_tag.audit.telemetry_auditor import TelemetryAuditor
from render_tag.common.resilience import retry_with_backoff
from render_tag.common.resources import ResourceStack
from render_tag.core.config import load_config
from render_tag.core.errors import WorkerStartupError
from render_tag.orchestration.persistent_worker import PersistentWorkerProcess
from render_tag.schema.hot_loop import CommandType, Response, ResponseStatus

logger = logging.getLogger(__name__)
console = Console()


def _signal_handler(sig, frame):
    """Handle termination signals by killing all active worker processes."""
    console.print(f"\n[bold red]Received signal {sig}. Terminating workers...[/bold red]")
    UnifiedWorkerOrchestrator.cleanup_all()
    console.print("[dim]Workers cleaned up. Exiting.[/dim]")
    sys.exit(1)


def get_completed_scene_ids(output_dir: Path) -> set[int]:
    """Identify completed scene IDs by scanning for sidecar JSON files."""
    completed_ids = set()
    images_dir = output_dir / "images"
    if not images_dir.exists():
        return completed_ids

    pattern = re.compile(r"scene_(\d+)(?:_cam_\d+)?_meta\.json")
    for f in images_dir.glob("*.json"):
        match = pattern.match(f.name)
        if match:
            completed_ids.add(int(match.group(1)))
    return completed_ids


def resolve_shard_index() -> int:
    """Auto-detect shard index from common Cloud environments."""
    for env_var in ["AWS_BATCH_JOB_ARRAY_INDEX", "CLOUD_RUN_TASK_INDEX", "JOB_COMPLETION_INDEX"]:
        if env_var in os.environ:
            return int(os.environ[env_var])
    return -1


def merge_csv_results(output_dir: Path):
    """Combine tags_shard_*.csv into tags.csv, preserving existing results."""
    logger.info("Merging worker results...")
    shards = sorted(list(output_dir.glob("tags_shard_*.csv")), key=lambda p: p.name)
    if not shards:
        return

    final_csv = output_dir / "tags.csv"
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
                    for line in infile:
                        outfile.write(line)
                shard_file.unlink()
        console.print(f"[dim]Merged {len(shards)} new shards into[/dim] {final_csv}")
    except Exception as e:
        console.print(f"[bold red]Failed to merge results:[/bold red] {e}")


class UnifiedWorkerOrchestrator:
    """Manages a pool of workers that can be either persistent or ephemeral."""

    _instances: ClassVar[list["UnifiedWorkerOrchestrator"]] = []

    def __init__(
        self,
        num_workers: int,
        base_port: int,
        blender_script: Path | None = None,
        blender_executable: str | None = None,
        use_blenderproc: bool = True,
        mock: bool = False,
        vram_threshold_mb: float | None = None,
        ephemeral: bool = False,
        max_renders_per_worker: int | None = None,
    ):
        self.num_workers = num_workers
        self.base_port = base_port
        if blender_script is None:
            self.blender_script = Path(__file__).resolve().parents[1] / "backend" / "zmq_server.py"
        else:
            self.blender_script = blender_script

        if blender_executable is None:
            if mock:
                self.blender_executable = sys.executable
                use_blenderproc = False
            else:
                self.blender_executable = "blenderproc"
        else:
            self.blender_executable = blender_executable

        self.use_blenderproc = use_blenderproc
        self.mock = mock
        self.vram_threshold_mb = vram_threshold_mb
        self.ephemeral = ephemeral
        self.max_renders_per_worker = max_renders_per_worker

        self.context = zmq.Context() if zmq else None
        self.workers: list[PersistentWorkerProcess] = []
        self.worker_queue = queue.Queue()
        self.auditor = TelemetryAuditor()
        self._lock = threading.Lock()
        self.running = False
        self._resource_stack = ResourceStack()
        UnifiedWorkerOrchestrator._instances.append(self)

    @classmethod
    def cleanup_all(cls):
        """Global cleanup for all active orchestrators."""
        for instance in list(cls._instances):
            instance.stop()
        cls._instances.clear()

    def _resolve_base_port(self, shard_id: str) -> int:
        """Dynamically resolve a base port to avoid conflicts."""
        import random

        seed_str = f"{shard_id}-{os.getpid()}-{random.random()}"
        port_offset = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 10000
        return self.base_port + port_offset

    @retry_with_backoff(
        retries=3, initial_delay=1.0, exceptions=(RuntimeError, WorkerStartupError)
    )
    def start(self, shard_id: str = "main"):
        """Starts the worker pool with retry logic."""
        with self._lock:
            if self.running:
                return

            resolved_port = self._resolve_base_port(shard_id)
            # Add a small random offset per attempt to avoid sticky conflicts
            import random

            current_base_port = resolved_port + random.randint(0, 50) * 10

            # Use a fresh stack for this attempt
            with ResourceStack() as attempt_stack:
                try:
                    logger.info(f"Starting pool on ports {current_base_port}+.")
                    self.workers.clear()
                    for i in range(self.num_workers):
                        worker = PersistentWorkerProcess(
                            worker_id=f"worker-{i}",
                            port=current_base_port + i,
                            blender_script=self.blender_script,
                            blender_executable=self.blender_executable,
                            use_blenderproc=self.use_blenderproc,
                            mock=self.mock,
                            max_renders=self.max_renders_per_worker,
                            context=self.context,
                        )
                        worker.start()
                        attempt_stack.push_resource(worker)
                        self.workers.append(worker)
                        self.worker_queue.put(worker)

                    # Handover stack to instance-level stack if successful
                    self._resource_stack.enter_context(attempt_stack.pop_all())
                    self.running = True
                except Exception as e:
                    raise WorkerStartupError(f"Failed to start worker pool: {e}") from e

    def stop(self):
        """Stops all workers."""
        with self._lock:
            if not self.running:
                return
            logger.info("Stopping UnifiedWorkerOrchestrator.")
            self._resource_stack.close()
            self.workers.clear()
            while not self.worker_queue.empty():
                try:
                    self.worker_queue.get_nowait()
                except queue.Empty:
                    break
            self.running = False

    def get_worker(self, timeout: float | None = None) -> PersistentWorkerProcess:
        return self.worker_queue.get(timeout=timeout)

    def release_worker(self, worker: PersistentWorkerProcess):
        should_restart = False
        from render_tag.schema.hot_loop import Telemetry

        is_healthy = False
        skip_check = self.ephemeral and self.max_renders_per_worker is not None

        # Staff Engineer: Ensure we record a baseline entry so auditor is never empty
        tel = Telemetry(
            vram_used_mb=0,
            vram_total_mb=0,
            cpu_usage_percent=0,
            state_hash="unknown",
            uptime_seconds=0,
        )

        try:
            if worker.client:
                if not skip_check:
                    resp = worker.send_command(CommandType.STATUS, timeout_ms=1000)
                    if resp.status == ResponseStatus.SUCCESS:
                        is_healthy = True
                        tel = Telemetry(**resp.data)
                else:
                    is_healthy = True

                self.auditor.add_entry(worker.worker_id, tel, event_type="render_complete")
                if self.vram_threshold_mb and tel.vram_used_mb > self.vram_threshold_mb:
                    should_restart = True
        except Exception:
            is_healthy = False

        if not is_healthy:
            should_restart = True
            # Add fallback entry if we didn't add one above
            if not is_healthy:
                self.auditor.add_entry(worker.worker_id, tel, event_type="render_complete_fallback")

        if should_restart and self.running:
            try:
                worker.stop()
                worker.start()
            except Exception as e:
                logger.error(f"Failed to restart {worker.worker_id}: {e}")
        self.worker_queue.put(worker)

    def execute_recipe(
        self,
        recipe: dict[str, Any],
        output_dir: Path,
        renderer_mode: str = "cycles",
        shard_id: str = "main",
    ) -> Response:
        worker = self.get_worker()
        try:
            return worker.send_command(
                CommandType.RENDER,
                payload={
                    "recipe": recipe,
                    "output_dir": str(output_dir),
                    "renderer_mode": renderer_mode,
                    "shard_id": shard_id,
                    "skip_visibility": self.mock,
                },
                timeout_ms=worker.client.timeout_ms,
            )
        finally:
            self.release_worker(worker)

    def __enter__(self):
        if not self.running:
            try:
                self.start()
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


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
    """Executes renders in parallel using a dynamic task pool."""
    from threading import Thread

    from ..generation.scene import Generator
    from .executors import ExecutorFactory

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    completed_ids = get_completed_scene_ids(output_dir) if resume else set()
    config = load_config(config_path)
    config.dataset.num_scenes = num_scenes

    generator = Generator(config, output_dir)
    all_recipes = generator.generate_all(exclude_ids=completed_ids)
    if not all_recipes:
        console.print("[yellow]No new scenes to generate.[/yellow]")
        return

    batches = []
    for i in range(0, len(all_recipes), batch_size):
        batch = all_recipes[i : i + batch_size]
        bid = i // batch_size
        path = generator.save_recipe_json(batch, f"recipes_batch_{bid}.json")
        batches.append((bid, path))

    executor = ExecutorFactory.get_executor(executor_type)
    task_queue = queue.Queue()
    for b in batches:
        task_queue.put(b)

    results = []

    def worker_thread(wid):
        while not task_queue.empty():
            try:
                bid, path = task_queue.get_nowait()
                executor.execute(path, output_dir, renderer_mode, f"batch_{bid}", verbose)
                results.append(True)
            except Exception as e:
                console.print(f"[bold red]Batch {bid} failed: {e}[/bold red]")
                results.append(False)
            finally:
                task_queue.task_done()

    threads = [Thread(target=worker_thread, args=(i,), daemon=True) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Staff Engineer: Raise Exit if any batch failed to satisfy CLI and tests
    if not all(results) and results:
        import typer

        raise typer.Exit(1)

    for _, path in batches:
        if path.exists():
            path.unlink()
    merge_csv_results(output_dir)
