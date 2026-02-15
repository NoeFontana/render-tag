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
    """Synchronous ZMQ client for communicating with Blender workers."""

    def __init__(self, port: int, context: "zmq.Context | None" = None, timeout_ms: int = 300000):
        self.port = port
        self.context = context or (zmq.Context() if zmq else None)
        self.timeout_ms = timeout_ms
        self.socket = None
        if self.context:
            self._recreate_socket()

    def _recreate_socket(self):
        """Recreate REQ socket to recover from timeout/EFSM states."""
        if not self.context:
            return
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
        if self.socket:
            self.socket.close()

    def send_command(
        self,
        command_type: CommandType,
        payload: dict[str, Any] | None = None,
        raise_on_failure: bool = False,
        timeout_ms: int | None = None,
        check_liveness: Any | None = None,
    ) -> Response:
        if not self.socket:
            raise WorkerCommunicationError("ZMQ not installed or socket not initialized")

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
        except zmq.Again as err:
            self._recreate_socket()
            raise WorkerCommunicationError(f"TIMEOUT sending {command_type}") from err
        finally:
            self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
