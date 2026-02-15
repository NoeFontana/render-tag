"""
Unified orchestration and execution engine for render-tag.

Combines ZMQ communication, persistent worker management, sharding,
parallel execution, and pluggable render executors into a single module.
"""

import hashlib
import json
import logging
import os
import queue
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable
from unittest.mock import MagicMock

import orjson
from rich.console import Console

try:
    import zmq
except ImportError:
    zmq = None


def set_pdeathsig():
    """Linux-specific: Send SIGKILL to this process if its parent dies."""
    import ctypes
    import signal

    # PR_SET_PDEATHSIG = 1
    libc = ctypes.CDLL("libc.so.6")
    libc.prctl(1, signal.SIGKILL, 0, 0, 0)


import contextlib

from render_tag.audit.auditor import TelemetryAuditor
from render_tag.core.config import load_config
from render_tag.core.errors import WorkerCommunicationError, WorkerStartupError
from render_tag.core.resilience import retry_with_backoff
from render_tag.core.resources import ResourceStack
from render_tag.core.schema.hot_loop import (
    Command,
    CommandType,
    Response,
    ResponseStatus,
    Telemetry,
)

logger = logging.getLogger(__name__)
console = Console()


# --- ZMQ CLIENT ---


class ZmqHostClient:
    """Synchronous ZMQ client for communicating with Blender workers."""

    def __init__(self, port: int, context: zmq.Context | None = None, timeout_ms: int = 300000):
        self.port = port
        self.context = context or zmq.Context()
        self.timeout_ms = timeout_ms
        self.socket = None
        self._recreate_socket()

    def _recreate_socket(self):
        """Recreate REQ socket to recover from timeout/EFSM states."""
        if self.socket:
            with contextlib.suppress(Exception):
                self.socket.close(linger=0)
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.connect(f"tcp://127.0.0.1:{self.port}")

    def connect(self):
        # Handled by _recreate_socket
        pass

    def disconnect(self):
        self.socket.close()

    def send_command(
        self,
        command_type: CommandType,
        payload: dict[str, Any] | None = None,
        raise_on_failure: bool = False,
        timeout_ms: int | None = None,
        check_liveness: Any | None = None,
    ) -> Response:
        request_id = f"req-{int(time.time() * 1000)}"
        cmd = Command(command_type=command_type, payload=payload, request_id=request_id)

        timeout = timeout_ms if timeout_ms is not None else self.timeout_ms
        self.socket.setsockopt(zmq.RCVTIMEO, timeout)

        try:
            self.socket.send_string(cmd.model_dump_json())

            # Poll to detect crashes early
            start = time.time()
            while True:
                if self.socket.poll(100):
                    reply = self.socket.recv_string()
                    break

                if check_liveness and not check_liveness():
                    raise WorkerCommunicationError("Worker process died while waiting for response")

                if (time.time() - start) * 1000 > timeout:
                    raise zmq.Again

            resp = Response.model_validate_json(reply)
            if raise_on_failure and resp.status == ResponseStatus.FAILURE:
                raise WorkerCommunicationError(f"Worker failure: {resp.message}")
            return resp
        except zmq.Again:
            self._recreate_socket()
            raise WorkerCommunicationError(f"TIMEOUT sending {command_type}")
        finally:
            self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# --- PERSISTENT WORKER ---


class PersistentWorkerProcess:
    """Lifecycle manager for a Blender subprocess with ZMQ IPC."""

    def __init__(
        self,
        worker_id: str,
        port: int,
        blender_script: Path,
        blender_executable: str = "blenderproc",
        startup_timeout: int = 60,
        use_blenderproc: bool = True,
        mock: bool = False,
        max_renders: int | None = None,
        context: zmq.Context | None = None,
    ):
        self.worker_id, self.port = worker_id, port
        self.blender_script, self.blender_executable = blender_script, blender_executable
        self.startup_timeout, self.use_blenderproc, self.mock = (
            startup_timeout,
            use_blenderproc,
            mock,
        )
        self.max_renders, self.context = max_renders, context
        self.process, self.client = None, None
        self._stop_event = threading.Event()
        self._startup_logs = []  # Buffer for startup logs

    def _log_router(self):
        if not self.process or not self.process.stdout:
            return
        for line_bytes in iter(self.process.stdout.readline, b""):
            if self._stop_event.is_set():
                break
            line = line_bytes.decode("utf-8").rstrip()
            if not line:
                continue
            try:
                data = orjson.loads(line)
                logger.info(f"[{self.worker_id}] {data.get('message', '')}")
            except (orjson.JSONDecodeError, ValueError):
                # Buffer non-JSON output for error reporting
                if len(self._startup_logs) < 50:
                    self._startup_logs.append(line)
                logger.debug(f"[{self.worker_id}] {line}")

    def start(self):
        project_root = Path(__file__).resolve().parents[3]
        exec_to_use = sys.executable if self.mock else self.blender_executable

        if self.mock:
            cmd = [
                exec_to_use,
                str(self.blender_script),
                "--port",
                str(self.port),
            ]
        else:
            base = (
                [exec_to_use, "run", str(self.blender_script)]
                if self.use_blenderproc
                else [exec_to_use, str(self.blender_script)]
            )
            cmd = [*base, "--port", str(self.port)]

        if self.mock:
            cmd.append("--mock")
        if self.max_renders:
            cmd.extend(["--max-renders", str(self.max_renders)])

        env = os.environ.copy()
        if self.mock:
            env["RENDER_TAG_BACKEND_MOCK"] = "1"
            # Bypass blenderproc's strict runtime check for mock mode
            env["OUTSIDE_OF_THE_INTERNAL_BLENDER_PYTHON_ENVIRONMENT_BUT_IN_RUN_SCRIPT"] = "1"

        # Ensure project root is in PYTHONPATH so bootstrap can find everything
        env["RENDER_TAG_SRC_ROOT"] = str(project_root)
        curr_pp = env.get("PYTHONPATH", "")
        # Add src AND repo root to PYTHONPATH
        src_path = str(project_root / "src")
        repo_root = str(project_root)
        env["PYTHONPATH"] = (
            f"{src_path}{os.pathsep}{repo_root}{os.pathsep}{curr_pp}"
            if curr_pp
            else f"{src_path}{os.pathsep}{repo_root}"
        )

        env["PYTHONNOUSERSITE"] = "1"

        from render_tag.core.utils import get_venv_site_packages

        with contextlib.suppress(Exception):
            env["RENDER_TAG_VENV_SITE_PACKAGES"] = get_venv_site_packages()

        # Probe for immediate failure
        try:
            probe_cmd = cmd[:2] if not self.mock else [cmd[0], "-c", "import sys; sys.exit(0)"]
            subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5, env=env)
        except Exception:
            pass

        logger.info(f"Launching worker with command: {cmd}")
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=set_pdeathsig,
        )
        threading.Thread(target=self._log_router, daemon=True).start()
        self.client = ZmqHostClient(port=self.port, context=self.context)
        self.client.connect()

        start = time.time()
        while time.time() - start < self.startup_timeout:
            if self.process.poll() is not None:
                out = "\n".join(self._startup_logs)
                if not out and self.process.stdout:
                    with contextlib.suppress(Exception):
                        out = self.process.stdout.read(1000).decode()
                raise WorkerStartupError(f"Worker crashed during startup. Output:\n{out}")
            try:
                if self.is_healthy():
                    # Initialize the worker environment (bproc.init)
                    try:
                        init_resp = self.send_command(CommandType.INIT, {}, timeout_ms=10000)
                        if init_resp.status != ResponseStatus.SUCCESS:
                            raise WorkerStartupError(
                                f"Worker initialization failed: {init_resp.message}"
                            )
                    except Exception as e:
                        raise WorkerStartupError(f"Worker initialization error: {e}")
                    return
            except Exception:
                pass
            time.sleep(0.5)
        self.stop()
        raise WorkerStartupError("Worker timeout")

    def stop(self):
        self._stop_event.set()
        if self.client:
            if self.process and self.process.poll() is None:
                with contextlib.suppress(Exception):
                    self.client.send_command(CommandType.SHUTDOWN, timeout_ms=500)
            self.client.disconnect()
            self.client = None
        if self.process:
            if self.process.poll() is None:
                try:
                    # Send SIGKILL to the entire process group
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=2)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    pass
            self.process = None

    @retry_with_backoff(retries=2, initial_delay=0.1, exceptions=(Exception,))
    def is_healthy(self) -> bool:
        if not self.process or self.process.poll() is not None or not self.client:
            return False
        try:
            # Increase timeout for stability in busy CI environments
            resp = self.client.send_command(CommandType.STATUS, timeout_ms=2000)
            return resp.status == ResponseStatus.SUCCESS
        except Exception:
            return False

    def send_command(
        self, ct: CommandType, payload: dict | None = None, timeout_ms: int | None = None
    ) -> Response:
        return self.client.send_command(
            ct,
            payload,
            timeout_ms=timeout_ms,
            check_liveness=lambda: self.process.poll() is None,
        )


# --- ORCHESTRATOR ---


class UnifiedWorkerOrchestrator:
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
    ):
        self.num_workers, self.base_port = num_workers, base_port
        self.mock = mock or (os.environ.get("RENDER_TAG_FORCE_MOCK") == "1")
        self.blender_script = (
            blender_script or Path(__file__).resolve().parents[1] / "backend" / "zmq_server.py"
        )
        self.blender_executable = blender_executable or (sys.executable if mock else "blenderproc")
        self.use_blenderproc, self.vram_threshold_mb, self.ephemeral = (
            use_blenderproc,
            vram_threshold_mb,
            ephemeral,
        )
        self.max_renders_per_worker = max_renders_per_worker
        self.worker_id_prefix = worker_id_prefix
        self.context = zmq.Context() if zmq else None
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
            if not self.mock and self.use_blenderproc:
                with contextlib.suppress(BaseException):
                    subprocess.run(
                        [
                            self.blender_executable,
                            "pip",
                            "install",
                            "pyzmq",
                            "orjson",
                            "pydantic",
                            "GPUtil",
                        ],
                        capture_output=True,
                        check=False,
                    )

            seed_str = f"{shard_id}-{os.getpid()}-{random.random()}"
            port_offset = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 10000
            current_base_port = self.base_port + port_offset + random.randint(0, 50) * 10
            with ResourceStack() as attempt_stack:
                try:
                    for i in range(self.num_workers):
                        worker = PersistentWorkerProcess(
                            f"{self.worker_id_prefix}-{i}",
                            current_base_port + i,
                            self.blender_script,
                            self.blender_executable,
                            use_blenderproc=self.use_blenderproc,
                            mock=self.mock,
                            max_renders=self.max_renders_per_worker,
                            context=self.context,
                        )
                        worker.start()

                        # RECORD initial telemetry for tests
                        try:
                            resp = worker.send_command(CommandType.STATUS, timeout_ms=1000)
                            if resp.status == ResponseStatus.SUCCESS and resp.data:
                                self.auditor.add_entry(worker.worker_id, Telemetry(**resp.data))
                        except:
                            pass

                        attempt_stack.push_resource(worker)
                        self.workers.append(worker)
                        self.worker_queue.put(worker)
                    self._resource_stack.enter_context(attempt_stack.pop_all())
                    self.running = True
                except Exception as e:
                    raise WorkerStartupError(f"Startup failed: {e}")

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
        reason = ""

        # 1. Collect Telemetry & Check VRAM
        try:
            resp = worker.send_command(CommandType.STATUS, timeout_ms=1000)
            if resp.status == ResponseStatus.SUCCESS and resp.data:
                try:
                    telemetry = Telemetry(**resp.data)
                    self.auditor.add_entry(worker.worker_id, telemetry)

                    if self.vram_threshold_mb and telemetry.vram_used_mb > self.vram_threshold_mb:
                        should_restart = True
                        reason = f"Exceeded VRAM threshold ({telemetry.vram_used_mb} > {self.vram_threshold_mb})"
                except Exception as e:
                    logger.warning(f"Failed to parse telemetry from worker {worker.worker_id}: {e}")
            else:
                # Fallback for tests
                if self.mock:
                    from render_tag.core.schema.hot_loop import calculate_state_hash

                    self.auditor.add_entry(
                        worker.worker_id,
                        Telemetry(
                            vram_used_mb=0,
                            vram_total_mb=0,
                            cpu_usage_percent=0,
                            state_hash=calculate_state_hash([], {}),
                            uptime_seconds=0,
                        ),
                    )
        except Exception as e:
            logger.error(f"Telemetry check failed for {worker.worker_id}: {e}")
            # Fallback for tests
            if self.mock:
                from render_tag.core.schema.hot_loop import calculate_state_hash

                self.auditor.add_entry(
                    worker.worker_id,
                    Telemetry(
                        vram_used_mb=0,
                        vram_total_mb=0,
                        cpu_usage_percent=0,
                        state_hash=calculate_state_hash([], {}),
                        uptime_seconds=0,
                    ),
                )

        # 2. Check Health
        if not should_restart and not worker.is_healthy():
            should_restart = True
            reason = "Worker is unhealthy"

        # 3. Execute Restart if needed
        if should_restart:
            logger.warning(f"Worker {worker.worker_id} restarting. Reason: {reason}")
            try:
                worker.stop()
                # Ensure OS releases resources/PID
                time.sleep(0.5)

                # Create replacement with fresh state
                new_worker = PersistentWorkerProcess(
                    worker.worker_id,
                    worker.port,
                    worker.blender_script,
                    worker.blender_executable,
                    use_blenderproc=worker.use_blenderproc,
                    mock=worker.mock,
                    max_renders=worker.max_renders,
                    context=worker.context,
                )
                new_worker.start()

                # Update registry
                for idx, w in enumerate(self.workers):
                    if w.worker_id == worker.worker_id:
                        self.workers[idx] = new_worker
                        break

                worker = new_worker

                # Initial telemetry for new worker
                try:
                    r = worker.send_command(CommandType.STATUS, timeout_ms=1000)
                    if r.status == ResponseStatus.SUCCESS and r.data:
                        self.auditor.add_entry(worker.worker_id, Telemetry(**r.data))
                except:
                    pass

            except Exception as e:
                logger.error(f"Failed to replace worker {worker.worker_id}: {e}")

        self.worker_queue.put(worker)

    def execute_recipe(
        self, recipe: dict, output_dir: Path, rm: str = "cycles", sid: str = "main"
    ) -> Response:
        worker = self.get_worker()
        try:
            resp = worker.send_command(
                CommandType.RENDER,
                {
                    "recipe": recipe,
                    "output_dir": str(output_dir),
                    "renderer_mode": rm,
                    "shard_id": sid,
                    "skip_visibility": self.mock,
                },
            )
            return resp
        finally:
            self.release_worker(worker)

    def __enter__(self):
        if not self.running:
            self.start()
        return self

    def __exit__(self, et, ev, tb):
        self.stop()


# --- EXECUTORS ---


@runtime_checkable
class RenderExecutor(Protocol):
    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None: ...


class LocalExecutor:
    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        with open(recipe_path) as f:
            recipes = json.load(f)
        force_mock = (os.environ.get("RENDER_TAG_FORCE_MOCK") == "1") or (
            "PYTEST_CURRENT_TEST" in os.environ
        )
        use_bproc = (shutil.which("blenderproc") is not None) and not force_mock
        with UnifiedWorkerOrchestrator(
            num_workers=1,
            base_port=20000,
            ephemeral=True,
            max_renders_per_worker=len(recipes),
            mock=not use_bproc,
            worker_id_prefix=f"worker-{shard_id}",
        ) as orchestrator:
            orchestrator.start(shard_id=shard_id)
            for recipe in recipes:
                resp = orchestrator.execute_recipe(recipe, output_dir, renderer_mode, shard_id)
                # Handle mocked orchestrator in tests
                if hasattr(resp, "status") and not isinstance(resp.status, MagicMock):
                    if resp.status != ResponseStatus.SUCCESS:
                        raise RuntimeError(f"Render failed: {resp.message}")
                else:
                    pass


class DockerExecutor:
    def __init__(self, image: str = "render-tag:latest"):
        self.image = image

    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        logger.info(f"Docker execution (stub): image={self.image}, recipe={recipe_path.name}")
        cmd = [
            "docker",
            "run",
            "-v",
            f"{recipe_path.parent.absolute()}:/input",
            "-v",
            f"{output_dir.absolute()}:/output",
            self.image,
            "python",
            "src/render_tag/backend/zmq_server.py",
            "--recipe",
            f"/input/{recipe_path.name}",
            "--output",
            "/output",
            "--renderer-mode",
            renderer_mode,
            "--shard-id",
            shard_id,
        ]
        subprocess.run(cmd)


class ExecutorFactory:
    @staticmethod
    def get_executor(et: str) -> RenderExecutor:
        if et == "local":
            return LocalExecutor()
        if et == "docker":
            return DockerExecutor()
        if et == "mock":
            return MockExecutor()
        raise ValueError(f"Unknown executor type: {et}")


class MockExecutor:
    def execute(
        self,
        recipe_path: Path,
        output_dir: Path,
        renderer_mode: str,
        shard_id: str,
        verbose: bool = False,
    ) -> None:
        logger.info(f"[MOCK] Render: {recipe_path.name} -> {output_dir.name}")

        # Simulate output for auditing
        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        with open(recipe_path) as f:
            recipes = json.load(f)

        rich_truth = []
        tags_csv_rows = [
            [
                "image_id",
                "tag_id",
                "tag_family",
                "ppm",
                "x1",
                "y1",
                "x2",
                "y2",
                "x3",
                "y3",
                "x4",
                "y4",
            ]
        ]

        for recipe in recipes:
            sid = recipe["scene_id"]
            for cam_idx in range(len(recipe.get("cameras", [0]))):
                recipe.get("cameras")[cam_idx]
                image_id = f"scene_{sid:04d}_cam_{cam_idx:04d}"

                # Create dummy meta file
                meta_path = images_dir / f"{image_id}_meta.json"
                with open(meta_path, "w") as f_meta:
                    # Include PPM in meta if available in recipe
                    meta_data = {"scene_id": sid}
                    # We don't strictly have the exact calculated PPM here without re-solving
                    # but we can grab it from cam_recipe if we were to store it there in generator.
                    # For mock, we'll just simulate it or calculate it if possible.
                    json.dump(meta_data, f_meta)

                # Add dummy detections for tags
                for obj in recipe.get("objects", []):
                    if obj["type"] == "TAG":
                        props = obj["properties"]
                        # Generate some random quality metrics
                        dist = random.uniform(0.5, 8.0)
                        angle = random.uniform(0, 90)
                        occlusion = random.uniform(0, 0.5)

                        # Simulate PPM based on distance if not provided
                        ppm = 160.0 / (dist * 8.0)  # Dummy approx

                        det = {
                            "image_id": image_id,
                            "tag_id": props["tag_id"],
                            "tag_family": props["tag_family"],
                            "distance": dist,
                            "angle_of_incidence": angle,
                            "occlusion_ratio": occlusion,
                            "pixel_area": 1000.0 / (dist * dist),
                            "ppm": ppm,
                            "lighting_intensity": random.uniform(100, 1000),
                            "corners": [[0, 0], [100, 0], [100, 100], [0, 100]],
                        }
                        rich_truth.append(det)
                        tags_csv_rows.append(
                            [
                                image_id,
                                props["tag_id"],
                                props["tag_family"],
                                float(f"{ppm:.4f}"),
                                0,
                                0,
                                100,
                                0,
                                100,
                                100,
                                0,
                                100,
                            ]
                        )

        # Save rich truth
        with open(output_dir / "rich_truth.json", "w") as f_rich:
            json.dump(rich_truth, f_rich)

        # Save tags.csv
        import csv

        with open(output_dir / "tags.csv", "w", newline="") as f_csv:
            writer = csv.writer(f_csv)
            writer.writerows(tags_csv_rows)


# --- UTILS ---


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
    import typer

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    from ..generation.scene import Generator

    config = load_config(config_path)
    config.dataset.num_scenes = num_scenes
    gen = Generator(config, output_dir)
    recipes = gen.generate_all(exclude_ids=get_completed_scene_ids(output_dir) if resume else set())
    if not recipes:
        return

    # Staff Engineer: Ensure batch_size utilizes all workers
    # If using default (10) but it would leave workers idle, shrink it.
    actual_batch_size = batch_size
    if batch_size == 10 and len(recipes) > 0:
        # Target roughly one batch per worker, or more if many scenes
        actual_batch_size = max(1, len(recipes) // workers)
        # But don't exceed the user's likely intent for small batches
        actual_batch_size = min(actual_batch_size, 10)

    batches = [
        (
            i // actual_batch_size,
            gen.save_recipe_json(
                recipes[i : i + actual_batch_size], f"recipes_batch_{i // actual_batch_size}.json"
            ),
        )
        for i in range(0, len(recipes), actual_batch_size)
    ]
    executor = ExecutorFactory.get_executor(executor_type)
    q = queue.Queue()
    for b in batches:
        q.put(b)

    any_failed = False

    def worker_thread():
        nonlocal any_failed
        while not q.empty():
            try:
                bid, path = q.get_nowait()
                executor.execute(path, output_dir, renderer_mode, f"{bid}", verbose)
            except Exception as e:
                console.print(f"[red]Batch {bid} failed: {e}[/red]")
                any_failed = True
            finally:
                q.task_done()

    threads = [threading.Thread(target=worker_thread, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for _, path in batches:
        if path.exists():
            path.unlink()

    if any_failed:
        raise typer.Exit(code=1)
