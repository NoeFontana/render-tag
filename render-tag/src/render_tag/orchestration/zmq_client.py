"""
ZeroMQ Client for Host-to-Backend communication.
"""

import time
import zmq
from typing import Any, Dict, Optional
from render_tag.schema.hot_loop import Command, Response, CommandType

class ZmqHostClient:
    """
    Client for sending commands to a persistent Blender backend via ZeroMQ.
    """

    def __init__(self, host: str = "localhost", port: int = 5555, timeout_ms: int = 10000):
        self.address = f"tcp://{host}:{port}"
        self.timeout_ms = timeout_ms
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.connected = False

    def connect(self):
        """Connects to the ZMQ backend."""
        self.socket.connect(self.address)
        self.connected = True

    def disconnect(self):
        """Closes the ZMQ connection."""
        self.socket.close()
        self.context.term()
        self.connected = False

    def send_command(self, command_type: CommandType, payload: Optional[Dict[str, Any]] = None) -> Response:
        """
        Sends a command and waits for a response.
        """
        request_id = f"req-{int(time.time() * 1000)}"
        command = Command(
            command_type=command_type,
            payload=payload,
            request_id=request_id
        )
        
        try:
            # Send JSON-serialized command
            self.socket.send_string(command.model_dump_json())
            
            # Wait for response
            response_json = self.socket.recv_string()
            return Response.model_validate_json(response_json)
            
        except zmq.Again:
            return Response(
                status="FAILURE",
                request_id=request_id,
                message=f"Timeout waiting for response from {self.address}"
            )
        except Exception as e:
            return Response(
                status="FAILURE",
                request_id=request_id,
                message=str(e)
            )

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
