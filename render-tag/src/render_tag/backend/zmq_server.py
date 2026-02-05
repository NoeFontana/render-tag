"""
ZeroMQ Server running inside Blender for Hot Loop optimization.
"""

import os
import sys
import time
import json
import logging
import zmq
import GPUtil
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    import bpy
    import blenderproc as bproc
except ImportError:
    bpy = None
    bproc = None

from render_tag.schema.hot_loop import Command, Response, ResponseStatus, CommandType, Telemetry, calculate_state_hash
from render_tag.backend.scene import setup_background

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
        
        if bproc and bpy:
            bproc.init()
            # Ensure we start with a clean scene
            bproc.clean_up()

    def get_telemetry(self) -> Telemetry:
        """Collects backend telemetry."""
        vram_used = 0.0
        vram_total = 0.0
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                # Use the first GPU for now
                gpu = gpus[0]
                vram_used = gpu.memoryUsed
                vram_total = gpu.memoryTotal
        except Exception as e:
            logger.debug(f"Could not get GPU telemetry: {e}")

        return Telemetry(
            vram_used_mb=vram_used,
            vram_total_mb=vram_total,
            cpu_usage_percent=0.0, # psutil could be used here
            state_hash=calculate_state_hash(self.assets_loaded, self.parameters),
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
            payload = cmd.payload or {}
            assets = payload.get("assets", [])
            parameters = payload.get("parameters", {})
            
            # Warm-up: Load assets into memory
            new_assets = []
            for asset_path in assets:
                if asset_path not in self.assets_loaded:
                    p = Path(asset_path)
                    if not p.exists():
                        return Response(
                            status=ResponseStatus.FAILURE,
                            request_id=cmd.request_id,
                            message=f"Asset not found: {asset_path}"
                        )
                    
                    if p.suffix.lower() in [".exr", ".hdr"]:
                        if bpy:
                            setup_background(p)
                            new_assets.append(asset_path)
                    # Add more asset types as needed (textures, models)
            
            self.assets_loaded.extend(new_assets)
            self.parameters.update(parameters)
            
            return Response(
                status=ResponseStatus.SUCCESS,
                request_id=cmd.request_id,
                message=f"Initialized with {len(new_assets)} new assets, {len(self.assets_loaded)} total resident.",
                data={"state_hash": calculate_state_hash(self.assets_loaded, self.parameters)}
            )

        return Response(
            status=ResponseStatus.FAILURE,
            request_id=cmd.request_id,
            message=f"Command {cmd.command_type} not implemented"
        )

    def run(self):
        """Main server loop."""
        self.running = True
        logger.info(f"Backend ZMQ Server started on port {self.port}")
        
        while self.running:
            try:
                if self.socket.poll(1000):
                    message = self.socket.recv_string()
                    cmd = Command.model_validate_json(message)
                    resp = self.handle_command(cmd)
                    self.socket.send_string(resp.model_dump_json())
            except Exception as e:
                logger.error(f"Error in server loop: {e}")
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    server = ZmqBackendServer(port=args.port)
    try:
        server.run()
    except KeyboardInterrupt:
        server.stop()