"""
Unified orchestration engine for render-tag.

Handles worker pool management, sharding, and parallel execution.
"""

import hashlib
import json
import os
import queue
import random
import re
import shutil
import signal
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from rich.console import Console

try:
    import zmq
except ImportError:
    zmq = None

from render_tag.audit.auditor import TelemetryAuditor
from render_tag.core.errors import WorkerCommunicationError, WorkerStartupError
from render_tag.core.logging import get_logger
from render_tag.core.resources import (
    ResourceStack,
    calculate_worker_memory_budget,
    get_thread_budget,
)
from render_tag.core.schema.hot_loop import (
    CommandType,
    Response,
    ResponseStatus,
    Telemetry,
    WorkerStatus,
)
from render_tag.core.schema.job import JobSpec
from render_tag.core.utils import is_port_in_use
from render_tag.orchestration.worker import PersistentWorkerProcess

logger = get_logger(__name__)
console = Console()


@dataclass(frozen=True)
class OrchestratorConfig:
    """Immutable configuration for the UnifiedWorkerOrchestrator.

    Attributes:
        num_workers: Number of parallel Blender processes to maintain.
        base_port: Starting port for ZMQ communication.
        blender_script: Path to the worker bootstrap script.
        blender_executable: Path to the Blender or BlenderProc binary.
        use_blenderproc: Whether to use the BlenderProc wrapper.
        mock: If True, uses mocks instead of a real Blender process.
        vram_threshold_mb: VRAM limit for preventative worker restarts.
        ephemeral: If True, workers are optimized for short-lived jobs.
        max_renders_per_worker: Restart worker after this many renders.
        worker_id_prefix: Prefix for naming worker processes.
        seed: Global random seed for deterministic generation.
        memory_limit_mb: Soft RAM limit per worker process.
    """

    num_workers: int = 1
    base_port: int = 20000
    blender_script: Path | None = None
    blender_executable: str | None = None
    use_blenderproc: bool = True
    mock: bool = False
    vram_threshold_mb: float | None = None
    ephemeral: bool = False
    max_renders_per_worker: int | None = None
    worker_id_prefix: str = "worker"
    seed: int = 42
    memory_limit_mb: int | None = None

    def __post_init__(self):
        """Handle default path for blender_script if not provided."""
        if self.blender_script is None:
            pass


class UnifiedWorkerOrchestrator:
    """Manages a pool of persistent Blender workers."""

    _instances: ClassVar[list["UnifiedWorkerOrchestrator"]] = []

    def __init__(self, config: OrchestratorConfig | None = None, **kwargs):
        if config is None:
            # Fallback for backwards compatibility or quick instantiation
            config = OrchestratorConfig(**kwargs)
        self.config = config

        self.mock = self.config.mock or (os.environ.get("RENDER_TAG_FORCE_MOCK") == "1")
        self.blender_script = (
            self.config.blender_script
            or Path(__file__).resolve().parents[3] / "scripts" / "worker_bootstrap.py"
        )
        self.blender_executable = self.config.blender_executable or (
            sys.executable if self.mock else "blenderproc"
        )

        self.job_id = str(uuid.uuid4())
        self.context = zmq.Context() if zmq else None
        self.thread_budget = get_thread_budget(num_workers=self.config.num_workers)
        self.workers, self.worker_queue = [], queue.Queue()
        self.auditor = TelemetryAuditor()
        self._lock, self.running = threading.Lock(), False
        self._resource_stack = ResourceStack()
        UnifiedWorkerOrchestrator._instances.append(self)

    @property
    def num_workers(self) -> int:
        return self.config.num_workers

    @property
    def base_port(self) -> int:
        return self.config.base_port

    @property
    def use_blenderproc(self) -> bool:
        return self.config.use_blenderproc

    @property
    def vram_threshold_mb(self) -> float | None:
        return self.config.vram_threshold_mb

    @property
    def ephemeral(self) -> bool:
        return self.config.ephemeral

    @property
    def max_renders_per_worker(self) -> int | None:
        return self.config.max_renders_per_worker

    @property
    def worker_id_prefix(self) -> str:
        return self.config.worker_id_prefix

    @property
    def seed(self) -> int:
        return self.config.seed

    @property
    def memory_limit_mb(self) -> int | None:
        return self.config.memory_limit_mb

    @classmethod
    def cleanup_all(cls):
        """Stop all active orchestrator instances and their workers."""
        for i in list(cls._instances):
            i.stop()
        cls._instances.clear()

    def start(self, shard_id: str = "main"):
        """Initialize the worker pool and start persistent processes.

        Calculates memory budgets, verifies port availability, and launches workers
        in parallel.

        Args:
            shard_id: Optional identifier for the current work shard.

        Raises:
            WorkerStartupError: If workers fail to initialize or contact the bridge.
        """
        with self._lock:
            if self.running:
                return

            seed_str = f"{shard_id}-{os.getpid()}-{random.random()}"
            port_offset = (
                int(hashlib.md5(seed_str.encode(), usedforsecurity=False).hexdigest(), 16) % 10000
            )
            current_base_port = self.base_port + port_offset + random.randint(0, 50) * 10
            # Calculate memory budget per worker
            effective_memory_limit = calculate_worker_memory_budget(
                num_workers=self.num_workers, explicit_limit_mb=self.memory_limit_mb
            )

            # Port scanning: Ensure the entire range is free
            for _ in range(10):
                if any(
                    is_port_in_use(current_base_port + i)
                    or is_port_in_use(current_base_port + i + 100)
                    for i in range(self.num_workers)
                ):
                    current_base_port += 200  # Shift by a safe margin
                    continue
                break

            with ResourceStack() as attempt_stack:
                try:
                    for i in range(self.num_workers):
                        unique_shard_id = f"{i}_{uuid.uuid4().hex[:6]}"
                        worker = PersistentWorkerProcess(
                            f"{self.worker_id_prefix}-{i}",
                            current_base_port + i,
                            self.blender_script,
                            self.blender_executable,
                            use_blenderproc=self.use_blenderproc,
                            mock=self.mock,
                            max_renders=self.max_renders_per_worker,
                            shard_id=unique_shard_id,
                            context=self.context,
                            thread_budget=self.thread_budget,
                            seed=self.config.seed,
                            job_id=self.job_id,
                            memory_limit_mb=effective_memory_limit,
                        )
                        worker.start()

                        # Record initial telemetry
                        try:
                            resp = worker.send_command(CommandType.STATUS, timeout_ms=1000)
                            if resp.status == ResponseStatus.SUCCESS and resp.data:
                                self.auditor.add_entry(worker.worker_id, Telemetry(**resp.data))
                        except Exception:
                            pass

                        attempt_stack.push_resource(worker)
                        self.workers.append(worker)
                        self.worker_queue.put(worker)
                    self._resource_stack.enter_context(attempt_stack.pop_all())
                    self.running = True
                except Exception as e:
                    raise WorkerStartupError(f"Startup failed: {e}") from e

    def stop(self):
        """Shutdown all workers and release resources."""
        with self._lock:
            if not self.running:
                return

            logger.info("Stopping Orchestrator and shutting down workers...")
            self._resource_stack.close()
            self.workers.clear()

            while not self.worker_queue.empty():
                try:
                    self.worker_queue.get_nowait()
                except queue.Empty:
                    break

            if self.context:
                logger.debug("Terminating ZMQ context...")
                try:
                    # FORCE CLOSE ALL SOCKETS with linger=0.
                    # This is the nuclear option to prevent hangs if any socket was leaked
                    # or if a worker is stuck.
                    self.context.destroy(linger=0)
                    logger.debug("ZMQ context destroyed.")
                except Exception as e:
                    logger.warning(f"Error destroying ZMQ context: {e}")
                self.context = None

            if self in UnifiedWorkerOrchestrator._instances:
                UnifiedWorkerOrchestrator._instances.remove(self)

            self.running = False
            logger.info("Orchestrator stopped.")

    def get_worker(self) -> PersistentWorkerProcess:
        """Acquire an available worker from the queue (blocking)."""
        return self.worker_queue.get()

    def release_worker(self, worker: PersistentWorkerProcess):
        """Return a worker to the pool, handling health checks and restarts.

        If a worker has exceeded its render limit or resource threshold, it is
        restarted before being returned to the queue.
        """
        intentional_exit = (
            worker.max_renders is not None and worker.renders_completed >= worker.max_renders
        )

        should_restart, limit_exceeded = self._check_worker_health(worker, intentional_exit)

        if should_restart or intentional_exit:
            worker = self._restart_worker(worker, limit_exceeded)

        self.worker_queue.put(worker)

    def _check_worker_health(
        self, worker: PersistentWorkerProcess, intentional_exit: bool
    ) -> tuple[bool, bool]:
        """Check if a worker needs to be restarted due to health or resource limits."""
        should_restart = False
        limit_exceeded = False

        if worker.client:
            try:
                resp = worker.send_command(CommandType.STATUS, timeout_ms=2500)
                if resp.status == ResponseStatus.SUCCESS and resp.data:
                    telemetry = Telemetry(**resp.data)
                    self.auditor.add_entry(worker.worker_id, telemetry)

                    # Check for memory or VRAM limits
                    if telemetry.status == WorkerStatus.RESOURCE_LIMIT_EXCEEDED:
                        limit_exceeded = True
                        should_restart = True
                    elif (
                        not intentional_exit
                        and self.vram_threshold_mb
                        and telemetry.vram_used_mb > self.vram_threshold_mb
                    ):
                        should_restart = True
            except Exception as e:
                if not intentional_exit:
                    logger.error(f"Telemetry check failed for {worker.worker_id}: {e}")

        if (
            not should_restart
            and not intentional_exit
            and (not worker.client or not worker.process or not worker.is_healthy())
        ):
            should_restart = True

        return should_restart, limit_exceeded

    def _restart_worker(
        self, worker: PersistentWorkerProcess, limit_exceeded: bool
    ) -> PersistentWorkerProcess:
        """Stop and restart a worker process."""
        if limit_exceeded:
            logger.info(f"Preventative restart for {worker.worker_id} (Resource limit exceeded)")

        worker.stop()
        slot_id = worker.shard_id.split("_")[0]
        unique_shard_id = f"{slot_id}_{uuid.uuid4().hex[:6]}"
        new_worker = PersistentWorkerProcess(
            worker.worker_id,
            worker.port,
            self.blender_script,
            self.blender_executable,
            use_blenderproc=self.use_blenderproc,
            mock=self.mock,
            max_renders=self.max_renders_per_worker,
            shard_id=unique_shard_id,
            context=self.context,
            thread_budget=self.thread_budget,
            seed=self.config.seed,
            job_id=self.job_id,
            memory_limit_mb=worker.memory_limit_mb,
        )
        new_worker.start()

        # Replace in active workers list
        for idx, w in enumerate(self.workers):
            if w.worker_id == worker.worker_id:
                self.workers[idx] = new_worker
                break
        return new_worker

    def execute_recipe(
        self, recipe: dict, output_dir: Path, rm: str = "cycles", sid: str | None = None
    ) -> Response:
        """Execute a single render job on an available worker.

        Handles retries for transient failures and resource exhaustion.

        Args:
            recipe: The JSON-serializable scene description.
            output_dir: Path where the rendered artifacts will be saved.
            rm: Renderer mode ('cycles', 'eevee', 'workbench').
            sid: Optional shard ID for the render task.

        Returns:
            The worker response containing status and metadata.

        Raises:
            WorkerCommunicationError: If the render fails after all retries.
        """
        max_retries = 2
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            worker = self.get_worker()
            try:
                effective_shard_id = sid if sid is not None else worker.shard_id
                resp = worker.send_command(
                    CommandType.RENDER,
                    {
                        "recipe": recipe,
                        "output_dir": str(output_dir),
                        "renderer_mode": rm,
                        "shard_id": effective_shard_id,
                        "skip_visibility": self.mock,
                    },
                )

                # Check for memory limit exceeded during render
                # In this case, we don't count it as a failed attempt
                if (
                    resp.status == ResponseStatus.FAILURE
                    and resp.message
                    and "RESOURCE_LIMIT_EXCEEDED" in resp.message
                ):
                    logger.info(
                        f"Worker {worker.worker_id} exceeded resource limits during render. "
                        "Retrying."
                    )
                    worker.stop()
                    # Do not increment attempt counter
                    continue

                if resp.status == ResponseStatus.SUCCESS:
                    worker.renders_completed += 1
                return resp
            except Exception as e:
                last_error = e
                logger.warning(f"Render attempt {attempt + 1} failed for {worker.worker_id}: {e}")
                worker.stop()
                attempt += 1
            finally:
                self.release_worker(worker)

        raise WorkerCommunicationError(
            f"Execute recipe failed after {max_retries} retries: {last_error}"
        )

    def __enter__(self):
        """Context manager entry: starts the orchestrator."""
        if not self.running:
            self.start()
        return self

    def __exit__(self, et, ev, tb):
        """Context manager exit: stops the orchestrator."""
        self.stop()


def get_completed_scene_ids(output_dir: Path) -> set[int]:
    """Scan output directory for completed scene metadata files."""
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
    """Resolve the current shard index from cloud environment variables."""
    for ev in ["AWS_BATCH_JOB_ARRAY_INDEX", "CLOUD_RUN_TASK_INDEX", "JOB_COMPLETION_INDEX"]:
        if ev in os.environ:
            return int(os.environ[ev])
    return -1


def _signal_handler(sig, frame):
    UnifiedWorkerOrchestrator.cleanup_all()
    sys.exit(0)


def _prepare_batches(job_spec: JobSpec, workers: int, batch_size: int, resume: bool):
    """Calculate shards and generate recipe batch files."""
    from render_tag.generation.scene import Generator
    from render_tag.orchestration.validator import ShardValidator

    output_dir = job_spec.paths.output_dir
    gen = Generator(job_spec.scene_config, output_dir, global_seed=job_spec.global_seed)

    # Calculate shard plan
    actual_batch_size = (
        min(batch_size, max(1, job_spec.shard_size // workers)) if batch_size == 5 else batch_size
    )
    total_shards = job_spec.get_total_shards(actual_batch_size)

    validator = ShardValidator(output_dir)
    missing_shard_indices = (
        validator.get_missing_shard_indices(
            num_shards=total_shards,
            scenes_per_shard=actual_batch_size,
            total_scenes=job_spec.shard_size,
        )
        if resume
        else list(range(total_shards))
    )

    if not missing_shard_indices:
        return None, actual_batch_size, total_shards

    batches = []
    for shard_idx in missing_shard_indices:
        # Generate recipes for this shard
        recipes = gen.generate_shards(
            total_scenes=job_spec.shard_size,
            shard_index=shard_idx,
            total_shards=total_shards,
            exclude_ids=get_completed_scene_ids(output_dir) if resume else set(),
        )
        if recipes:
            batch_path = gen.save_recipe_json(recipes, f"recipes_shard_{shard_idx}.json")
            batches.append(batch_path)

    return batches, actual_batch_size, total_shards


def _run_orchestration_loop(
    orchestrator: UnifiedWorkerOrchestrator,
    batches: list[Path],
    workers: int,
    output_dir: Path,
    rm: str,
) -> bool:
    """Run the parallel orchestration loop using a worker pool."""
    logger.info(f"Starting orchestration loop with {len(batches)} batches and {workers} workers.")
    q = queue.Queue()
    for path in batches:
        q.put(path)

    any_failed = False

    def worker_thread():
        nonlocal any_failed
        while not q.empty():
            try:
                path = q.get_nowait()
                with open(path) as f:
                    batch_recipes = json.load(f)

                logger.debug(f"Worker thread processing batch: {path.name}")
                for recipe in batch_recipes:
                    m = re.search(r"shard_(\d+)", path.name)
                    shard_idx_str = m.group(1) if m else "0"

                    resp = orchestrator.execute_recipe(recipe, output_dir, rm, sid=shard_idx_str)
                    if resp.status != ResponseStatus.SUCCESS:
                        console.print(f"[red]Render failed: {resp.message}[/red]")
                        any_failed = True
                logger.debug(f"Worker thread finished batch: {path.name}")
            except queue.Empty:
                break
            except Exception as e:
                console.print(f"[red]Batch processing failed: {e}[/red]")
                logger.error(f"Batch processing failed: {e}", exc_info=True)
                any_failed = True
            finally:
                q.task_done()

    threads = [threading.Thread(target=worker_thread, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()

    logger.info(f"Waiting for {len(threads)} worker threads to complete...")
    for t in threads:
        t.join()

    logger.info("Orchestration loop completed.")
    return any_failed


def orchestrate(
    job_spec: JobSpec,
    workers: int = 1,
    executor_type: str = "local",
    resume: bool = False,
    batch_size: int = 5,
    verbose: bool = False,
) -> None:
    """Main orchestration loop for executing a JobSpec.

    Handles sharding, resumption, and parallel execution of render tasks.

    Args:
        job_spec: Detailed specification of the rendering job.
        workers: Number of parallel worker processes to spawn.
        executor_type: Infrastructure target ('local', 'cloud').
        resume: If True, skips already completed scenes.
        batch_size: Number of recipes per worker batch.
        verbose: If True, enables debug logging.

    Raises:
        typer.Exit: With code 1 if any render tasks failed.
    """
    import typer

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    output_dir = job_spec.paths.output_dir
    batches, _, _ = _prepare_batches(job_spec, workers, batch_size, resume)

    if batches is None:
        console.print("[green]All shards are already complete. Skipping orchestration.[/green]")
        return

    if not batches:
        return

    rm = job_spec.scene_config.renderer.mode if job_spec.scene_config.renderer else "cycles"
    force_mock = (os.environ.get("RENDER_TAG_FORCE_MOCK") == "1") or (
        "PYTEST_CURRENT_TEST" in os.environ
    )
    use_bproc = (shutil.which("blenderproc") is not None) and not force_mock

    config = OrchestratorConfig(
        num_workers=workers,
        ephemeral=True,
        max_renders_per_worker=batch_size,
        mock=not use_bproc,
        seed=job_spec.global_seed,
        memory_limit_mb=job_spec.infrastructure.max_memory_mb,
    )

    with UnifiedWorkerOrchestrator(config=config) as orchestrator:
        any_failed = _run_orchestration_loop(orchestrator, batches, workers, output_dir, rm)

    for path in batches:
        if path.exists():
            path.unlink()

    if any_failed:
        raise typer.Exit(code=1)
