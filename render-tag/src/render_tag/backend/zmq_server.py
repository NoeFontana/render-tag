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
from typing import Dict, Any, List, Optional

from render_tag.backend.bridge import bproc, bpy, np, bridge
from render_tag.schema.hot_loop import Command, Response, ResponseStatus, CommandType, Telemetry, calculate_state_hash
from render_tag.backend.scene import setup_background
from render_tag.backend.render_loop import execute_recipe
from render_tag.backend.assets import global_pool
from render_tag.data_io.writers import (
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)

logger = logging.getLogger(__name__)

class ZmqBackendServer:
    """
    Persistent backend server running inside Blender.
    """

    def __init__(self, port: int = 5555, bproc_mock=None, bpy_mock=None):
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{port}")
        self.running = False
        self.assets_loaded = []
        self.parameters = {}
        self.start_time = time.time()
        
        if bproc_mock or bpy_mock:
            bridge.inject_mocks(bproc_mock, bpy_mock)

        # Persistent writers to avoid file handle overhead
        self.current_output_dir: Optional[Path] = None
        self.writers: Dict[str, Any] = {}
        
        if bridge.bproc and bridge.bpy:
            try:
                bridge.bproc.init()
                bridge.bproc.clean_up()
            except Exception:
                pass

    def get_telemetry(self) -> Telemetry:
        """Collects backend telemetry."""
        vram_used = 0.0
        vram_total = 0.0
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                vram_used = gpu.memoryUsed
                vram_total = gpu.memoryTotal
        except Exception:
            pass

        return Telemetry(
            vram_used_mb=vram_used,
            vram_total_mb=vram_total,
            cpu_usage_percent=0.0,
            state_hash=calculate_state_hash(self.assets_loaded, self.parameters),
            uptime_seconds=time.time() - self.start_time
        )

    def _setup_writers(self, output_dir: Path):
        """Initializes or updates persistent writers for an output directory."""
        if self.current_output_dir == output_dir:
            return
            
        self.current_output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.writers = {
            "csv": CSVWriter(output_dir / "tags_hot_loop.csv"),
            "coco": COCOWriter(output_dir),
            "rich": RichTruthWriter(output_dir / "rich_truth.json"),
            "sidecar": SidecarWriter(output_dir)
        }

    def handle_command(self, cmd: Command) -> Response:
        """Processes a single command."""
        logger.info(f"Handling command: {cmd.command_type}")
        
        try:
            if cmd.command_type == CommandType.STATUS:
                return Response(
                    status=ResponseStatus.SUCCESS,
                    request_id=cmd.request_id,
                    message="Backend is alive",
                    data=self.get_telemetry().model_dump()
                )
            
            elif cmd.command_type == CommandType.SHUTDOWN:
                self.running = False
                # Finalize writers
                if "coco" in self.writers:
                    self.writers["coco"].save()
                if "rich" in self.writers:
                    self.writers["rich"].save()
                return Response(
                    status=ResponseStatus.SUCCESS,
                    request_id=cmd.request_id,
                    message="Shutting down..."
                )
                
            elif cmd.command_type == CommandType.INIT:
                payload = cmd.payload or {}
                assets = payload.get("assets", [])
                parameters = payload.get("parameters", {})
                
                new_assets = []
                for asset_path in assets:
                    if asset_path not in self.assets_loaded:
                        p = Path(asset_path)
                        if p.exists() and p.suffix.lower() in [".exr", ".hdr"]:
                            if bridge.bpy: setup_background(p)
                            new_assets.append(asset_path)
                
                self.assets_loaded.extend(new_assets)
                self.parameters.update(parameters)
                
                return Response(
                    status=ResponseStatus.SUCCESS,
                    request_id=cmd.request_id,
                    message=f"Initialized. {len(self.assets_loaded)} assets resident.",
                    data={"state_hash": calculate_state_hash(self.assets_loaded, self.parameters)}
                )

            elif cmd.command_type == CommandType.RENDER:
                payload = cmd.payload or {}
                recipe = payload.get("recipe")
                output_dir = payload.get("output_dir")
                renderer_mode = payload.get("renderer_mode", "cycles")
                skip_visibility = payload.get("skip_visibility", False)
                
                if not recipe or not output_dir:
                    return Response(
                        status=ResponseStatus.FAILURE,
                        request_id=cmd.request_id,
                        message="Missing recipe or output_dir in RENDER payload"
                    )

                self._setup_writers(Path(output_dir))
                
                # Execute the recipe using our reusable loop
                execute_recipe(
                    recipe,
                    Path(output_dir),
                    renderer_mode,
                    self.writers["csv"],
                    self.writers["coco"],
                    self.writers["rich"],
                    self.writers["sidecar"],
                    skip_visibility=skip_visibility
                )
                
                return Response(
                    status=ResponseStatus.SUCCESS,
                    request_id=cmd.request_id,
                    message=f"Rendered scene {recipe['scene_id']}",
                    data={"state_hash": calculate_state_hash(self.assets_loaded, self.parameters)}
                )

            elif cmd.command_type == CommandType.RESET:
                # Partial reset: Just clear the object pool
                global_pool.release_all()
                return Response(
                    status=ResponseStatus.SUCCESS,
                    request_id=cmd.request_id,
                    message="Volatile state reset (object pool cleared).",
                    data={"state_hash": calculate_state_hash(self.assets_loaded, self.parameters)}
                )

        except Exception as e:
            logger.error(f"Error executing {cmd.command_type}: {e}", exc_info=True)
            return Response(
                status=ResponseStatus.FAILURE,
                request_id=cmd.request_id,
                message=str(e)
            )

        return Response(
            status=ResponseStatus.FAILURE,
            request_id=cmd.request_id,
            message=f"Command {cmd.command_type} not implemented"
        )

    def run(self, max_renders: Optional[int] = None):
        """
        Main server loop.
        
        Args:
            max_renders: If set, the server will shutdown after this many successful RENDER commands.
                         Used for 'Ephemeral Worker' mode.
        """
        self.running = True
        renders_completed = 0
        logger.info(f"Backend ZMQ Server started on port {self.port}")
        if max_renders:
            logger.info(f"Running in ephemeral mode (max_renders={max_renders})")
        
        while self.running:
            try:
                if self.socket.poll(1000):
                    message = self.socket.recv_string()
                    cmd = Command.model_validate_json(message)
                    resp = self.handle_command(cmd)
                    self.socket.send_string(resp.model_dump_json())
                    
                    if cmd.command_type == CommandType.RENDER and resp.status == ResponseStatus.SUCCESS:
                        renders_completed += 1
                        if max_renders and renders_completed >= max_renders:
                            logger.info(f"Reached max_renders ({max_renders}). Shutting down soon.")
                            # Give host a tiny bit of time to collect final telemetry
                            time.sleep(1.0)
                            self.running = False
                            # Finalize writers
                            if "coco" in self.writers: self.writers["coco"].save()
                            if "rich" in self.writers: self.writers["rich"].save()

            except Exception as e:
                logger.error(f"Error in server loop: {e}")
                pass

    def stop(self):
        self.running = False
        self.socket.close()
        self.context.term()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--max-renders", type=int, default=None, help="Shutdown after N renders")
    args = parser.parse_args()
    
    bproc_m, bpy_m = None, None
    if args.mock:
        # Add project root to path so we can import tests.mocks
        project_root = str(Path(__file__).resolve().parents[3])
        if project_root not in sys.path:
            sys.path.append(project_root)
        from tests.mocks import blenderproc_api as bproc_m
        from tests.mocks import blender_api as bpy_m

    logging.basicConfig(level=logging.INFO)
    server = ZmqBackendServer(port=args.port, bproc_mock=bproc_m, bpy_mock=bpy_m)
    try:
        server.run(max_renders=args.max_renders)
    except KeyboardInterrupt:
        server.stop()