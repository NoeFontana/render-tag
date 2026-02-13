"""
ZeroMQ Client for Host-to-Backend communication.
"""

import logging
import time
from typing import Any

try:
    import zmq
except ImportError:
    zmq = None

from render_tag.schema.hot_loop import Command, CommandType, Response

logger = logging.getLogger(__name__)


class ZmqHostClient:
    """
    Client for sending commands to a persistent Blender backend via ZeroMQ.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5555,
        timeout_ms: int = 120000,
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
        
        # Ensure timeout options are set BEFORE connecting
        if zmq:
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
        timeout_ms: int | None = None,
    ) -> Response:
        """
        Sends a command and waits for a response.
        If a timeout occurs, the socket is reset to maintain REQ/REP synchronization.
        """
        if not self.connected:
            self.connect()

        # Temporary timeout override
        original_timeout = self.socket.getsockopt(zmq.RCVTIMEO)
        if timeout_ms is not None:
            self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self.socket.setsockopt(zmq.SNDTIMEO, timeout_ms)

        request_id = f"req-{int(time.time() * 1000)}"
        command = Command(command_type=command_type, payload=payload, request_id=request_id)

        try:
            # Send JSON-serialized command
            logger.debug(f"Sending command {command_type} ({request_id}) to {self.address}")
            start_time = time.time()
            self.socket.send_string(command.model_dump_json())

            # Wait for response
            response_json = self.socket.recv_string()
            elapsed = time.time() - start_time
            logger.debug(f"Received response for {command_type} ({request_id}) in {elapsed:.3f}s")
            return Response.model_validate_json(response_json)

        except zmq.Again:
            # REQ/REP synchronization is broken on timeout. Must reset socket.
            elapsed = time.time() - start_time
            effective_timeout = timeout_ms if timeout_ms is not None else self.timeout_ms
            logger.error(f"TIMEOUT sending command {command_type} ({request_id}) after {elapsed:.3f}s (timeout_cfg={effective_timeout}ms)")
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
        finally:
            # Restore original timeout
            if timeout_ms is not None and self.socket:
                self.socket.setsockopt(zmq.RCVTIMEO, original_timeout)
                self.socket.setsockopt(zmq.SNDTIMEO, original_timeout)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
