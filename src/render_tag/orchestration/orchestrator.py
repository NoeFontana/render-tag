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
from render_tag.core.resources import ResourceStack, get_thread_budget
from render_tag.core.schema.hot_loop import CommandType, Response, ResponseStatus, Telemetry
from render_tag.core.schema.job import JobSpec
from render_tag.orchestration.worker import PersistentWorkerProcess

logger = get_logger(__name__)
console = Console()


class UnifiedWorkerOrchestrator:
    """Manages a pool of persistent Blender workers."""

    _instances: ClassVar[list["UnifiedWorkerOrchestrator"]] = []

    def __init__(
        self,
        num_workers: int = 1,
        base_port: int = 20000,
        blender_script: Path | None = None,
        blender_executable: str | None = None,
        use_blenderproc: bool = True,
        mock: bool = False,
        vram_threshold_mb: float | None = None,
        ephemeral: bool = False,
        max_renders_per_worker: int | None = None,
        worker_id_prefix: str = "worker",
        seed: int = 42,
    ):
        self.num_workers, self.base_port = num_workers, base_port
        self.mock = mock or (os.environ.get("RENDER_TAG_FORCE_MOCK") == "1")
        self.blender_script = (
            blender_script
            or Path(__file__).resolve().parents[3] / "scripts" / "worker_bootstrap.py"
        )
        self.blender_executable = blender_executable or (sys.executable if mock else "blenderproc")
        self.use_blenderproc, self.vram_threshold_mb, self.ephemeral = (
            use_blenderproc,
            vram_threshold_mb,
            ephemeral,
        )
        self.max_renders_per_worker = max_renders_per_worker
        self.worker_id_prefix = worker_id_prefix
        self.seed = seed
        self.job_id = str(uuid.uuid4())
        self.context = zmq.Context() if zmq else None
        self.thread_budget = get_thread_budget(num_workers=self.num_workers)
        self.workers, self.worker_queue = [], queue.Queue()
        self.auditor = TelemetryAuditor()
        self._lock, self.running = threading.Lock(), False
        self._resource_stack = ResourceStack()
        UnifiedWorkerOrchestrator._instances.append(self)

    @classmethod
    def cleanup_all(cls):
        for i in list(cls._instances):
            i.stop()
        cls._instances.clear()

    def start(self, shard_id: str = "main"):
        with self._lock:
            if self.running:
                return

            seed_str = f"{shard_id}-{os.getpid()}-{random.random()}"
            port_offset = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 10000
            current_base_port = self.base_port + port_offset + random.randint(0, 50) * 10

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
                            seed=self.seed,
                            job_id=self.job_id,
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
        with self._lock:
            if not self.running:
                return
            self._resource_stack.close()
            self.workers.clear()
            while not self.worker_queue.empty():
                try:
                    self.worker_queue.get_nowait()
                except queue.Empty:
                    break
            self.running = False

    def get_worker(self) -> PersistentWorkerProcess:
        return self.worker_queue.get()

    def release_worker(self, worker: PersistentWorkerProcess):
        should_restart = False
        intentional_exit = (
            worker.max_renders is not None and worker.renders_completed >= worker.max_renders
        )

        if worker.client:
            try:
                resp = worker.send_command(CommandType.STATUS, timeout_ms=2500)
                if resp.status == ResponseStatus.SUCCESS and resp.data:
                    telemetry = Telemetry(**resp.data)
                    self.auditor.add_entry(worker.worker_id, telemetry)
                    if (
                        not intentional_exit
                        and self.vram_threshold_mb
                        and telemetry.vram_used_mb > self.vram_threshold_mb
                    ):
                        should_restart = True
            except Exception as e:
                if not intentional_exit:
                    logger.error(f"Telemetry check failed for {worker.worker_id}: {e}")

        if not should_restart and not intentional_exit:
            if not worker.client or not worker.process or not worker.is_healthy():
                should_restart = True

        if should_restart or intentional_exit:
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
                seed=self.seed,
                job_id=self.job_id,
            )
            new_worker.start()
            for idx, w in enumerate(self.workers):
                if w.worker_id == worker.worker_id:
                    self.workers[idx] = new_worker
                    break
            worker = new_worker

        self.worker_queue.put(worker)

    def execute_recipe(
        self, recipe: dict, output_dir: Path, rm: str = "cycles", sid: str | None = None
    ) -> Response:
        max_retries = 2
        last_error = None
        for attempt in range(max_retries + 1):
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
                if resp.status == ResponseStatus.SUCCESS:
                    worker.renders_completed += 1
                return resp
            except Exception as e:
                last_error = e
                logger.warning(f"Render attempt {attempt + 1} failed for {worker.worker_id}: {e}")
                worker.stop()
            finally:
                self.release_worker(worker)
        raise WorkerCommunicationError(
            f"Execute recipe failed after {max_retries} retries: {last_error}"
        )

    def __enter__(self):
        if not self.running:
            self.start()
        return self

    def __exit__(self, et, ev, tb):
        self.stop()


def get_completed_scene_ids(output_dir: Path) -> set[int]:
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
    for ev in ["AWS_BATCH_JOB_ARRAY_INDEX", "CLOUD_RUN_TASK_INDEX", "JOB_COMPLETION_INDEX"]:
        if ev in os.environ:
            return int(os.environ[ev])
    return -1


def _signal_handler(sig, frame):
    UnifiedWorkerOrchestrator.cleanup_all()
    sys.exit(0)


def orchestrate(
    job_spec: JobSpec,
    workers: int = 1,
    executor_type: str = "local",
    resume: bool = False,
    batch_size: int = 5,
    verbose: bool = False,
) -> None:
    import typer

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    from render_tag.generation.scene import Generator

    output_dir = job_spec.paths.output_dir
    gen = Generator(job_spec.scene_config, output_dir)
    recipes = gen.generate_all(exclude_ids=get_completed_scene_ids(output_dir) if resume else set())
    if not recipes:
        return

    actual_batch_size = (
        min(batch_size, max(1, len(recipes) // workers)) if batch_size == 5 else batch_size
    )
    batches = [
        gen.save_recipe_json(
            recipes[i : i + actual_batch_size], f"recipes_batch_{i // actual_batch_size}.json"
        )
        for i in range(0, len(recipes), actual_batch_size)
    ]

    rm = job_spec.scene_config.renderer.mode if job_spec.scene_config.renderer else "cycles"
    force_mock = (os.environ.get("RENDER_TAG_FORCE_MOCK") == "1") or (
        "PYTEST_CURRENT_TEST" in os.environ
    )
    use_bproc = (shutil.which("blenderproc") is not None) and not force_mock

    with UnifiedWorkerOrchestrator(
        num_workers=workers,
        ephemeral=True,
        max_renders_per_worker=batch_size,
        mock=not use_bproc,
        seed=job_spec.global_seed,
    ) as orchestrator:
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
                    for recipe in batch_recipes:
                        resp = orchestrator.execute_recipe(recipe, output_dir, rm)
                        if resp.status != ResponseStatus.SUCCESS:
                            console.print(f"[red]Render failed: {resp.message}[/red]")
                            any_failed = True
                except queue.Empty:
                    break
                except Exception as e:
                    console.print(f"[red]Batch processing failed: {e}[/red]")
                    any_failed = True
                finally:
                    q.task_done()

        threads = [threading.Thread(target=worker_thread, daemon=True) for _ in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    for path in batches:
        if path.exists():
            path.unlink()

    if any_failed:
        raise typer.Exit(code=1)
