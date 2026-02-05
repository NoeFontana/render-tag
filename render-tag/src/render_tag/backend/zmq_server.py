"""
ZeroMQ Server running inside Blender for Hot Loop optimization.
"""

import os
import sys
import time
import json
import logging
import zmq
from pathlib import Path
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from render_tag.schema.hot_loop import Command, Response, ResponseStatus, CommandType, Telemetry

logger = logging.getLogger(__name__)

class ZmqBackendServer:
    """
    Persistent backend server running inside Blender.
    """

    def __init__(self, port: int = 5555):
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{port}")
        self.running = False
        self.assets_loaded = []
        self.parameters = {}
        self.start_time = time.time()

    def get_telemetry(self) -> Telemetry:
        """Collects backend telemetry."""
        # TODO: Implement real VRAM/CPU monitoring via bpy or psutil
        return Telemetry(
            vram_used_mb=0.0,
            vram_total_mb=0.0,
            cpu_usage_percent=0.0,
            state_hash="skeleton-hash",
            uptime_seconds=time.time() - self.start_time
        )

    def handle_command(self, cmd: Command) -> Response:
        """Processes a single command."""
        logger.info(f"Handling command: {cmd.command_type}")
        
        if cmd.command_type == CommandType.STATUS:
            return Response(
                status=ResponseStatus.SUCCESS,
                request_id=cmd.request_id,
                message="Backend is alive",
                data=self.get_telemetry().model_dump()
            )
        
        elif cmd.command_type == CommandType.SHUTDOWN:
            self.running = False
            return Response(
                status=ResponseStatus.SUCCESS,
                request_id=cmd.request_id,
                message="Shutting down..."
            )
            
        elif cmd.command_type == CommandType.INIT:
            # Skeleton: just record assets
            assets = cmd.payload.get("assets", []) if cmd.payload else []
            self.assets_loaded.extend(assets)
            return Response(
                status=ResponseStatus.SUCCESS,
                request_id=cmd.request_id,
                message=f"Initialized with {len(assets)} assets"
            )

        return Response(
            status=ResponseStatus.FAILURE,
            request_id=cmd.request_id,
            message=f"Command {cmd.command_type} not implemented in skeleton"
        )

    def run(self):
        """Main server loop."""
        self.running = True
        logger.info(f"Backend ZMQ Server started on port {self.port}")
        
        while self.running:
            try:
                # Use poller to allow for timeouts/interrupts
                if self.socket.poll(1000):
                    message = self.socket.recv_string()
                    cmd = Command.model_validate_json(message)
                    resp = self.handle_command(cmd)
                    self.socket.send_string(resp.model_dump_json())
            except Exception as e:
                logger.error(f"Error in server loop: {e}")
                # Try to send failure response if we have a request_id
                # but in REQ/REP, we MUST send something back
                try:
                    error_resp = Response(
                        status=ResponseStatus.FAILURE,
                        request_id="error",
                        message=str(e)
                    )
                    self.socket.send_string(error_resp.model_dump_json())
                except:
                    pass

    def stop(self):
        self.running = False
        self.socket.close()
        self.context.term()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = ZmqBackendServer()
    try:
        server.run()
    except KeyboardInterrupt:
        server.stop()
