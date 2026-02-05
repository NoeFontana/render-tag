"""
Manager for a single persistent Blender worker process.
"""

import subprocess
import logging
import time
import zmq
from pathlib import Path
from typing import Optional, Dict, Any

from render_tag.orchestration.zmq_client import ZmqHostClient
from render_tag.schema.hot_loop import CommandType, ResponseStatus, Response

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
        mock: bool = False
    ):
        self.worker_id = worker_id
        self.port = port
        self.blender_script = blender_script
        self.blender_executable = blender_executable
        self.startup_timeout = startup_timeout
        self.use_blenderproc = use_blenderproc
        self.mock = mock
        
        self.process: Optional[subprocess.Popen] = None
        self.client: Optional[ZmqHostClient] = None

    def _get_process_output(self) -> str:
        """Helper to get process output safely if it has exited."""
        if not self.process:
            return ""
        try:
            # Only communicate if it's already dead or we're ready to wait
            stdout, stderr = self.process.communicate(timeout=0.1)
            return f"Stdout: {stdout}\nStderr: {stderr}"
        except Exception:
            return "Could not retrieve process output (still running or pipe error)"

    def start(self):
        """Spawns the Blender subprocess and waits for it to become ready."""
        if self.process and self.process.poll() is None:
            logger.warning(f"Worker {self.worker_id} is already running.")
            return

        base_cmd = []
        if self.use_blenderproc:
            base_cmd = [self.blender_executable, "run", str(self.blender_script)]
        else:
            base_cmd = [self.blender_executable, str(self.blender_script)]
        
        cmd = base_cmd + ["--port", str(self.port)]
        if self.mock:
            cmd.append("--mock")

        logger.info(f"Starting persistent worker {self.worker_id}: {' '.join(cmd)}")
        
        # We start the process. The script needs to accept --port
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Initialize ZMQ client with short timeout for startup phase
        self.client = ZmqHostClient(port=self.port, timeout_ms=1000)
        self.client.connect()

        # Wait for heartbeat/status success
        start_time = time.time()
        while time.time() - start_time < self.startup_timeout:
            poll_result = self.process.poll()
            if poll_result is not None:
                output = self._get_process_output()
                raise RuntimeError(f"Worker {self.worker_id} failed to start (exit {poll_result}).\n{output}")

            try:
                resp = self.client.send_command(CommandType.STATUS, raise_on_failure=True)
                if resp.status == ResponseStatus.SUCCESS:
                    logger.info(f"Worker {self.worker_id} is ready.")
                    # Restore default timeout for normal operation
                    self.client.socket.setsockopt(zmq.RCVTIMEO, 10000)
                    return
            except Exception:
                pass
                
            time.sleep(0.5)

        output = self._get_process_output()
        self.stop()
        raise TimeoutError(f"Worker {self.worker_id} timed out during startup.\n{output}")

    def stop(self):
        """Gracefully stops the worker."""
        if self.client:
            try:
                self.client.send_command(CommandType.SHUTDOWN)
                self.client.disconnect()
            except Exception:
                pass
            self.client = None

        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
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

    def send_command(self, command_type: CommandType, payload: Optional[Dict[str, Any]] = None) -> Response:
        """Sends a command to the worker."""
        if not self.is_healthy():
            raise RuntimeError(f"Worker {self.worker_id} is not healthy or not running.")
        
        return self.client.send_command(command_type, payload)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
