"""
Worker process management for render-tag.
"""

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import orjson

from render_tag.core.errors import WorkerCommunicationError, WorkerStartupError
from render_tag.core.logging import get_logger
from render_tag.core.resilience import retry_with_backoff
from render_tag.core.schema.hot_loop import CommandType, ResponseStatus, Response
from render_tag.core.utils import get_project_root, get_venv_site_packages
from render_tag.orchestration.client import ZmqHostClient


def set_worker_priority():
    """Linux-specific: Set process priority for workers and ensure death with parent."""
    import ctypes
    import os
    import signal

    # 1. De-escalate priority (niceness)
    with contextlib.suppress(Exception):
        os.nice(10)

    # 2. PR_SET_PDEATHSIG = 1
    with contextlib.suppress(Exception):
        libc = ctypes.CDLL("libc.so.6")
        libc.prctl(1, signal.SIGKILL, 0, 0, 0)


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
        shard_id: str = "main",
        context: Any = None,
        thread_budget: int = 1,
        seed: int = 42,
        job_id: str | None = None,
    ):
        self.worker_id, self.port = worker_id, port
        self.job_id = job_id
        self.blender_script, self.blender_executable = blender_script, blender_executable
        self.startup_timeout, self.use_blenderproc, self.mock = (
            startup_timeout,
            use_blenderproc,
            mock,
        )
        self.max_renders, self.shard_id, self.context = max_renders, shard_id, context
        self.thread_budget = thread_budget
        self.seed = seed
        self.process, self.client = None, None
        self.renders_completed = 0
        self._stop_event = threading.Event()
        self._startup_logs = []
        self.logger = get_logger(f"worker.{worker_id}").bind(worker_id=worker_id, job_id=job_id)

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
                self.logger.info(f"[{self.worker_id}] {data.get('message', '')}")
            except (orjson.JSONDecodeError, ValueError):
                if len(self._startup_logs) < 50:
                    self._startup_logs.append(line)
                self.logger.debug(f"[{self.worker_id}] {line}")

    def start(self):
        root = get_project_root()
        exec_to_use = sys.executable if self.mock else self.blender_executable

        if self.mock:
            cmd = [exec_to_use, str(self.blender_script), "--port", str(self.port)]
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
        if self.shard_id:
            cmd.extend(["--shard-id", str(self.shard_id)])
        cmd.extend(["--seed", str(self.seed)])

        env = os.environ.copy()
        if self.mock:
            env["RENDER_TAG_BACKEND_MOCK"] = "1"
            env["OUTSIDE_OF_THE_INTERNAL_BLENDER_PYTHON_ENVIRONMENT_BUT_IN_RUN_SCRIPT"] = "1"

        # Unified Environment Injection
        src_path = str(root / "src")
        repo_root = str(root)
        curr_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{repo_root}{os.pathsep}{curr_pp}".strip(os.pathsep)
        env["PYTHONNOUSERSITE"] = "1"
        env["OMP_NUM_THREADS"] = str(self.thread_budget)
        env["BLENDER_CPU_THREADS"] = str(self.thread_budget)
        
        venv_site = get_venv_site_packages()
        if venv_site:
            env["RENDER_TAG_VENV_SITE_PACKAGES"] = venv_site

        if self.job_id:
            env["RENDER_TAG_JOB_ID"] = self.job_id

        self.logger.info(f"Launching worker with command: {cmd}")
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=set_worker_priority,
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
                    init_resp = self.send_command(CommandType.INIT, {}, timeout_ms=10000)
                    if init_resp.status != ResponseStatus.SUCCESS:
                        raise WorkerStartupError(f"Worker initialization failed: {init_resp.message}")
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
