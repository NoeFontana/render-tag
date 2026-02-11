"""
Manager for a single persistent Blender worker process.
"""

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    import zmq
except ImportError:
    zmq = None

from render_tag.orchestration.zmq_client import ZmqHostClient
from render_tag.schema.hot_loop import CommandType, Response, ResponseStatus

logger = logging.getLogger(__name__)


class PersistentWorkerProcess:
    """
    Manages the lifecycle of a persistent Blender subprocess with ZMQ communication.
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

    def _get_process_output(self) -> str:
        """Helper to get process output safely if it has exited."""
        return "Process output capture disabled to prevent deadlocks."

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

        # Start the process. Inherit stdout/stderr so it propagates to parent
        # (and pytest captures it)
        self.process = subprocess.Popen(cmd, env=env, stdout=None, stderr=None, text=True)

        # Initialize ZMQ client with short timeout for startup phase
        self.client = ZmqHostClient(port=self.port, timeout_ms=1000, context=self.context)
        self.client.connect()
        # Wait for heartbeat/status success
        start_time = time.time()
        while time.time() - start_time < self.startup_timeout:
            poll_result = self.process.poll()
            if poll_result is not None and poll_result != 0:
                raise RuntimeError(f"Worker {self.worker_id} failed to start (exit {poll_result}).")
            
            if poll_result == 0:
                # Finished already
                return

            try:
                resp = self.client.send_command(CommandType.STATUS, raise_on_failure=True)
                if resp.status == ResponseStatus.SUCCESS:
                    logger.info(f"Worker {self.worker_id} is ready.")
                    # Restore default timeout for normal operation
                    self.client.socket.setsockopt(zmq.RCVTIMEO, 10000)
                    return
                else:
                    logger.warning(
                        f"Worker {self.worker_id} replied but status is {resp.status}: "
                        f"{resp.message}"
                    )
            except Exception as e:
                logger.warning(f"Worker {self.worker_id} not ready yet (attempt): {e}")
                pass

            time.sleep(0.5)

        self.stop()
        raise TimeoutError(f"Worker {self.worker_id} timed out during startup.")

    def stop(self):
        """Gracefully stops the worker."""
        if self.client:
            try:
                # Only try to send SHUTDOWN if process is still alive
                if self.process and self.process.poll() is None:
                    # Use a very short timeout for shutdown command
                    self.client.socket.setsockopt(zmq.RCVTIMEO, 500)
                    self.client.send_command(CommandType.SHUTDOWN)

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

    def is_healthy(self) -> bool:
        """Checks if the worker is still alive and responsive."""
        if not self.process or self.process.poll() is not None:
            return False

        if not self.client:
            return False

        resp = self.client.send_command(CommandType.STATUS)
        return resp.status == ResponseStatus.SUCCESS

    def send_command(
        self, command_type: CommandType, payload: dict[str, Any] | None = None
    ) -> Response:
        """Sends a command to the worker."""
        if not self.is_healthy():
            raise RuntimeError(f"Worker {self.worker_id} is not healthy or not running.")

        return self.client.send_command(command_type, payload)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
