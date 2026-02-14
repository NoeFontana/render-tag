"""
Manager for a single persistent Blender worker process.
"""

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

try:
    import zmq
except ImportError:
    zmq = None

import orjson
from tqdm import tqdm

from render_tag.common.resilience import retry_with_backoff
from render_tag.core.errors import WorkerCommunicationError
from render_tag.orchestration.zmq_client import ZmqHostClient
from render_tag.schema.hot_loop import CommandType, Response, ResponseStatus

logger = logging.getLogger(__name__)


class PersistentWorkerProcess:
    """
    Manages the lifecycle of a persistent Blender subprocess with ZMQ communication.
    Now includes a structured Log Router for JSON IPC.
    """

    def __init__(
        self,
        worker_id: str,
        port: int,
        blender_script: Path,
        blender_executable: str = "blenderproc",
        startup_timeout: int = 30,
        use_blenderproc: bool = True,
        mock: bool = False,
        max_renders: int | None = None,
        context: zmq.Context | None = None,
    ):
        self.worker_id = worker_id
        self.port = port
        self.blender_script = blender_script
        self.blender_executable = blender_executable
        self.startup_timeout = startup_timeout
        self.use_blenderproc = use_blenderproc
        self.mock = mock
        self.max_renders = max_renders
        self.context = context

        self.process: subprocess.Popen | None = None
        self.client: ZmqHostClient | None = None

        # Structured Logging
        self._log_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pbar: tqdm | None = None
        self._raw_log_file: Any | None = None

    def _get_process_output(self) -> str:
        """Helper to get process output safely if it has exited."""
        return "Process output capture handled by Log Router."

    def _log_router(self):
        """
        Reads NDJSON from the subprocess stdout/stderr and routes it.
        """
        if not self.process:
            return
            
        stdout = self.process.stdout
        if not stdout:
            return

        for line_bytes in iter(stdout.readline, b""):
            if self._stop_event.is_set():
                break

            line = line_bytes.decode("utf-8").rstrip()
            if not line:
                continue

            try:
                # Try to parse as JSON
                data = orjson.loads(line)

                # Route based on type
                log_type = data.get("type", "log")
                message = data.get("message", "")
                payload = data.get("payload", {})

                if log_type == "progress":
                    self._update_progress(payload)
                elif log_type == "metric":
                    m_name = payload.get("metric")
                    m_val = payload.get("value")
                    m_unit = payload.get("unit")
                    logger.debug(f"[{self.worker_id}] METRIC: {m_name} = {m_val} {m_unit}")
                elif log_type == "error":
                    logger.error(f"[{self.worker_id}] BACKEND ERROR: {message}")
                else:
                    # Regular log
                    level = data.get("level", "INFO")
                    log_func = getattr(logger, level.lower(), logger.info)
                    log_func(f"[{self.worker_id}] {message}")

            except orjson.JSONDecodeError:
                # Non-JSON output (Blender noise)
                if self._raw_log_file:
                    self._raw_log_file.write(f"{line}\n")
                    self._raw_log_file.flush()

    def _update_progress(self, payload: dict[str, Any]):
        """Updates or creates a tqdm progress bar."""
        current = payload.get("current", 0)
        total = payload.get("total", 100)
        scene_id = payload.get("scene_id", "unknown")

        if not self._pbar:
            self._pbar = tqdm(
                total=total,
                desc=f"Worker {self.worker_id} (Scene {scene_id})",
                leave=False,
                unit="cam",
            )

        self._pbar.n = current
        self._pbar.refresh()

        if current >= total:
            self._pbar.close()
            self._pbar = None

    def start(self):
        """Spawns the Blender subprocess and waits for it to become ready."""
        if self.process and self.process.poll() is None:
            logger.warning(f"Worker {self.worker_id} is already running.")
            return

        base_cmd = []
        if self.use_blenderproc:
            base_cmd = [self.blender_executable, "run", str(self.blender_script)]
        else:
            # If not using blenderproc (e.g. standard python for mocks),
            # just run the script directly.
            base_cmd = [self.blender_executable, str(self.blender_script)]

        cmd = [*base_cmd, "--port", str(self.port)]
        if self.mock:
            cmd.append("--mock")
        if self.max_renders:
            cmd.extend(["--max-renders", str(self.max_renders)])

        logger.info(f"Starting persistent worker {self.worker_id}: {' '.join(cmd)}")

        # Clean environment to prevent Blender from picking up host venv packages
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        if self.mock:
            env["RENDER_TAG_BACKEND_MOCK"] = "1"

        # Inject venv site-packages so the backend bootstrap can find them
        from render_tag.common.utils import get_venv_site_packages

        venv_site = get_venv_site_packages()
        if venv_site:
            env["RENDER_TAG_VENV_SITE_PACKAGES"] = venv_site
            logger.debug(f"Injected RENDER_TAG_VENV_SITE_PACKAGES: {venv_site}")

        # Ensure strict isolation from system-wide Python packages
        env["PYTHONNOUSERSITE"] = "1"

        # Add project src to PYTHONPATH so render_tag package can be imported
        # Assuming script is at src/render_tag/backend/zmq_server.py
        # We want to add 'src' to path.
        project_src = self.blender_script.resolve().parents[2]
        python_paths = []

        if self.mock:
            # Add tests/mocks/ to PYTHONPATH so 'import blenderproc' finds our mock
            project_root = project_src.parent
            mocks_dir = project_root / "tests" / "mocks"
            if mocks_dir.exists():
                python_paths.append(str(mocks_dir))
            # Also add project root so 'tests.mocks' imports work
            python_paths.append(str(project_root))

        if project_src.name == "src":
            python_paths.append(str(project_src))

        if python_paths:
            env["PYTHONPATH"] = ":".join(python_paths)

        # Ensure raw log file is open
        if not self._raw_log_file:
            self._raw_log_file = open("blender_raw.log", "a")  # noqa: SIM115

        # Start the process with piped output
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,  # Use bytes for efficiency
        )

        # Start Log Router Thread
        self._stop_event.clear()
        self._log_thread = threading.Thread(target=self._log_router, daemon=True)
        self._log_thread.start()

        # Initialize ZMQ client
        self.client = ZmqHostClient(port=self.port, context=self.context)
        self.client.connect()
        # Wait for heartbeat/status success
        start_time = time.time()
        while time.time() - start_time < self.startup_timeout:
            # CHECK PROCESS FIRST
            poll_result = self.process.poll()
            if poll_result is not None and poll_result != 0:
                self.stop()  # Cleanup threads
                raise RuntimeError(f"Worker {self.worker_id} failed to start (exit {poll_result}).")

            if poll_result == 0:
                # Finished already
                return

            try:
                # Use a slightly longer timeout for the initial status check
                # (Blender init can be slow)
                resp = self.client.send_command(
                    CommandType.STATUS, raise_on_failure=True, timeout_ms=5000
                )
                if resp.status == ResponseStatus.SUCCESS:
                    logger.info(f"Worker {self.worker_id} is ready.")
                    return
                else:
                    logger.warning(
                        f"Worker {self.worker_id} replied but status is {resp.status}: "
                        f"{resp.message}"
                    )
            except Exception as e:
                logger.debug(f"Worker {self.worker_id} not ready yet (attempt): {e}")
                pass

            time.sleep(0.5)

        self.stop()
        raise TimeoutError(f"Worker {self.worker_id} timed out during startup.")

    def stop(self):
        """Gracefully stops the worker."""
        self._stop_event.set()

        if self.client:
            try:
                # Only try to send SHUTDOWN if process is still alive
                # Staff Engineer: Use a very short timeout and handle already-exited processes
                if self.process and self.process.poll() is None:
                    try:
                        self.client.send_command(CommandType.SHUTDOWN, timeout_ms=200)
                    except Exception:
                        pass

                self.client.disconnect()
            except Exception:
                pass
            self.client = None

        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None

        if self._log_thread:
            self._log_thread.join(timeout=1.0)
            self._log_thread = None

        if self._pbar:
            self._pbar.close()
            self._pbar = None

    @retry_with_backoff(retries=2, initial_delay=0.1, backoff_factor=1.5, exceptions=(Exception,))
    def is_healthy(self) -> bool:
        """Checks if the worker is still alive and responsive."""
        if not self.process or self.process.poll() is not None:
            return False

        if not self.client:
            return False

        resp = self.client.send_command(
            CommandType.STATUS, timeout_ms=self.client.timeout_ms
        )
        return resp.status == ResponseStatus.SUCCESS

    def send_command(
        self,
        command_type: CommandType,
        payload: dict[str, Any] | None = None,
        timeout_ms: int | None = None,
    ) -> Response:
        """Sends a command to the worker."""
        if not self.is_healthy():
            raise RuntimeError(f"Worker {self.worker_id} is not healthy or not running.")

        return self.client.send_command(command_type, payload, timeout_ms=timeout_ms)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __del__(self):
        try:
            if hasattr(self, "_raw_log_file") and self._raw_log_file:
                self._raw_log_file.close()
        except Exception:
            pass
