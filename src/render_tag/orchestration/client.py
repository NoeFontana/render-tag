"""
ZMQ Client for Host-to-Worker communication.
"""

import contextlib
import time
from typing import Any

try:
    import zmq
except ImportError:
    zmq = None

from render_tag.core.errors import WorkerCommunicationError
from render_tag.core.schema.hot_loop import (
    Command,
    CommandType,
    Response,
    ResponseStatus,
)


class ZmqHostClient:
    """Robust ZMQ client with Dual-Socket Architecture (Task + Management)."""

    def __init__(
        self,
        port: int,
        mgmt_port: int | None = None,
        context: "zmq.Context | None" = None,
        timeout_ms: int = 300000,
        heartbeat_interval_s: float = 10.0,
    ):
        self.port = port
        self.mgmt_port = mgmt_port or (port + 100)
        self.owns_context = context is None
        self.context = context or (zmq.Context() if zmq else None)
        self.timeout_ms = timeout_ms
        self.heartbeat_interval_s = heartbeat_interval_s
        self.task_socket = None
        self.mgmt_socket = None
        if self.context:
            self._recreate_sockets()

    def _recreate_sockets(self):
        """Recreate sockets to recover from timeout/EFSM states."""
        if not self.context:
            return

        # Close existing
        for sock in [self.task_socket, self.mgmt_socket]:
            if sock:
                with contextlib.suppress(Exception):
                    sock.close(linger=0)

        # 1. Task Socket (REQ)
        self.task_socket = self.context.socket(zmq.REQ)
        self.task_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.task_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.task_socket.setsockopt(zmq.LINGER, 0)
        self.task_socket.connect(f"tcp://127.0.0.1:{self.port}")

        # 2. Management Socket (REQ)
        self.mgmt_socket = self.context.socket(zmq.REQ)
        self.mgmt_socket.setsockopt(zmq.RCVTIMEO, 5000)  # Short timeout for heartbeats
        self.mgmt_socket.setsockopt(zmq.SNDTIMEO, 5000)
        self.mgmt_socket.setsockopt(zmq.LINGER, 0)
        self.mgmt_socket.connect(f"tcp://127.0.0.1:{self.mgmt_port}")

    def connect(self):
        # Handled by _recreate_sockets
        pass

    def disconnect(self):
        if self.task_socket:
            with contextlib.suppress(Exception):
                self.task_socket.close(linger=0)
            self.task_socket = None
        if self.mgmt_socket:
            with contextlib.suppress(Exception):
                self.mgmt_socket.close(linger=0)
            self.mgmt_socket = None
        
        if self.owns_context and self.context:
            with contextlib.suppress(Exception):
                self.context.term()
            self.context = None

    def _check_heartbeat(self) -> bool:
        """Query management channel to see if worker is alive."""
        if not self.mgmt_socket:
            return False

        req_id = f"hb-{int(time.time() * 1000)}"
        cmd = Command(command_type=CommandType.STATUS, request_id=req_id)

        try:
            self.mgmt_socket.send_string(cmd.model_dump_json())
            if self.mgmt_socket.poll(2000):
                self.mgmt_socket.recv_string()
                return True
            return False
        except Exception:
            return False
        finally:
            # Always recreate mgmt socket on failure/timeout to clear EFSM
            if not self.mgmt_socket.poll(0):
                self._recreate_mgmt_socket()

    def _recreate_mgmt_socket(self):
        if not self.context:
            return
        with contextlib.suppress(Exception):
            self.mgmt_socket.close(linger=0)
        self.mgmt_socket = self.context.socket(zmq.REQ)
        self.mgmt_socket.setsockopt(zmq.RCVTIMEO, 5000)
        self.mgmt_socket.setsockopt(zmq.LINGER, 0)
        self.mgmt_socket.connect(f"tcp://127.0.0.1:{self.mgmt_port}")

    def send_command(
        self,
        command_type: CommandType,
        payload: dict[str, Any] | None = None,
        raise_on_failure: bool = False,
        timeout_ms: int | None = None,
        check_liveness: Any | None = None,
    ) -> Response:
        if not self.task_socket:
            raise WorkerCommunicationError("ZMQ not installed or socket not initialized")

        request_id = f"req-{int(time.time() * 1000)}"
        cmd = Command(command_type=command_type, payload=payload, request_id=request_id)

        timeout = timeout_ms if timeout_ms is not None else self.timeout_ms
        self.task_socket.setsockopt(zmq.RCVTIMEO, timeout)
        self.task_socket.setsockopt(zmq.SNDTIMEO, timeout)

        try:
            self.task_socket.send_string(cmd.model_dump_json())

            start = time.time()
            last_heartbeat = start

            # Polling Loop with Heartbeats
            while True:
                # 1. Check if response is ready
                if self.task_socket.poll(100):
                    reply = self.task_socket.recv_string()
                    break

                # 2. Check process liveness (OS level)
                if check_liveness and not check_liveness():
                    raise WorkerCommunicationError("Worker process died while waiting for response")

                # 3. Dynamic Heartbeat (System level)
                now = time.time()
                if (now - last_heartbeat) > self.heartbeat_interval_s:
                    if not self._check_heartbeat():
                        # Worker is unresponsive even on the management channel
                        raise WorkerCommunicationError(f"Worker unresponsive during {command_type}")
                    last_heartbeat = now
                    # RESET timer on successful heartbeat to allow indefinite execution
                    # as long as worker is responsive.
                    start = now

                # 4. Global Timeout (Safety valve)
                if (now - start) * 1000 > timeout:
                    raise zmq.Again

            resp = Response.model_validate_json(reply)
            if raise_on_failure and resp.status == ResponseStatus.FAILURE:
                raise WorkerCommunicationError(f"Worker failure: {resp.message}")
            return resp
        except zmq.Again as err:
            self._recreate_sockets()
            raise WorkerCommunicationError(f"TIMEOUT sending {command_type}") from err
        except Exception as e:
            if not isinstance(e, WorkerCommunicationError):
                self._recreate_sockets()
            raise
        finally:
            self.task_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
            self.task_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
