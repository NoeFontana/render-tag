"""
ZeroMQ Client for Host-to-Backend communication.
"""

import time
from typing import Any

try:
    import zmq
except ImportError:
    zmq = None

from render_tag.schema.hot_loop import Command, CommandType, Response


class ZmqHostClient:
    """
    Client for sending commands to a persistent Blender backend via ZeroMQ.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5555,
        timeout_ms: int = 10000,
        context: zmq.Context | None = None,
    ):
        self.address = f"tcp://{host}:{port}"
        self.timeout_ms = timeout_ms
        self.context = context or zmq.Context()
        self._own_context = context is None
        self.socket = None
        self.connected = False

    def _create_socket(self):
        """Creates and configures the ZMQ socket."""
        if self.socket:
            self.socket.close(linger=0)
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.connect(self.address)

    def connect(self):
        """Connects to the ZMQ backend."""
        self._create_socket()
        self.connected = True

    def disconnect(self):
        """Closes the ZMQ connection."""
        if self.socket:
            self.socket.close(linger=0)
        if self._own_context:
            self.context.term()
        self.connected = False

    def send_command(
        self,
        command_type: CommandType,
        payload: dict[str, Any] | None = None,
        raise_on_failure: bool = False,
    ) -> Response:
        """
        Sends a command and waits for a response.
        If a timeout occurs, the socket is reset to maintain REQ/REP synchronization.
        """
        if not self.connected:
            self.connect()

        request_id = f"req-{int(time.time() * 1000)}"
        command = Command(command_type=command_type, payload=payload, request_id=request_id)

        try:
            # Send JSON-serialized command
            self.socket.send_string(command.model_dump_json())

            # Wait for response
            response_json = self.socket.recv_string()
            return Response.model_validate_json(response_json)

        except zmq.Again:
            # REQ/REP synchronization is broken on timeout. Must reset socket.
            self._create_socket()
            if raise_on_failure:
                raise TimeoutError(f"Timeout waiting for response from {self.address}") from None
            return Response(
                status="FAILURE",
                request_id=request_id,
                message=f"Timeout waiting for response from {self.address}",
            )
        except Exception as e:
            # Reset socket on any major error to be safe
            self._create_socket()
            if raise_on_failure:
                raise e
            return Response(status="FAILURE", request_id=request_id, message=str(e))

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
