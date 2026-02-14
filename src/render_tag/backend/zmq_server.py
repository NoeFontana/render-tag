"""
ZMQ Backend Server for render-tag.

Acts as a persistent Blender process that receives rendering recipes
via ZMQ and executes them, returning telemetry and status.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Protocol

import zmq

from render_tag.backend.assets import global_pool
from render_tag.backend.bridge import bridge
from render_tag.backend.render_loop import execute_recipe
from render_tag.backend.scene import setup_background
from render_tag.data_io.writers import (
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)
from render_tag.schema.hot_loop import (
    Command,
    CommandType,
    Response,
    ResponseStatus,
    Telemetry,
    calculate_state_hash,
)

try:
    import GPUtil
except ImportError:
    GPUtil = None

logger = logging.getLogger(__name__)


class CommandHandler(Protocol):
    """Protocol for backend command handlers."""

    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        """Process the command and return a response."""
        ...


class StatusHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message="Backend is alive",
            data=server.get_telemetry().model_dump(),
        )


class InitHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        payload = cmd.payload or {}
        assets = payload.get("assets", [])
        parameters = payload.get("parameters", {})

        new_assets = []
        for asset_path in assets:
            if asset_path not in server.assets_loaded:
                p = Path(asset_path)
                if p.exists() and p.suffix.lower() in [".exr", ".hdr"]:
                    if bridge.bpy:
                        setup_background(p)
                    new_assets.append(asset_path)

        server.assets_loaded.extend(new_assets)
        server.parameters.update(parameters)

        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message=f"Initialized. {len(server.assets_loaded)} assets resident.",
            data={"state_hash": calculate_state_hash(server.assets_loaded, server.parameters)},
        )


class RenderHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        payload = cmd.payload or {}
        recipe = payload.get("recipe")
        output_dir = payload.get("output_dir")
        renderer_mode = payload.get("renderer_mode", "cycles")
        shard_id = payload.get("shard_id", "main")
        skip_visibility = payload.get("skip_visibility", False)

        if not recipe or not output_dir:
            return Response(
                status=ResponseStatus.FAILURE,
                request_id=cmd.request_id,
                message="Missing recipe or output_dir in RENDER payload",
            )

        server._setup_writers(Path(output_dir), shard_id=shard_id)

        # Execute the recipe using our reusable loop
        execute_recipe(
            recipe,
            Path(output_dir),
            renderer_mode,
            server.writers["csv"],
            server.writers["coco"],
            server.writers["rich"],
            server.writers["sidecar"],
            skip_visibility=skip_visibility,
        )

        server.renders_completed += 1

        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message=f"Rendered scene {recipe['scene_id']}",
            data={"state_hash": calculate_state_hash(server.assets_loaded, server.parameters)},
        )


class ResetHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        global_pool.release_all()
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message="Volatile state reset (object pool cleared).",
            data={"state_hash": calculate_state_hash(server.assets_loaded, server.parameters)},
        )


class ShutdownHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        server.running = False
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message="Shutting down...",
        )


class ZmqBackendServer:
    """
    Persistent ZMQ server running inside Blender.
    Refactored to use Command Pattern for extensibility.
    """

    def __init__(self, port: int = 5555, bproc_mock=None, bpy_mock=None):
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://127.0.0.1:{port}")
        self.running = False
        self.assets_loaded = []
        self.parameters = {}
        self.start_time = time.time()
        self.renders_completed = 0

        # Command Dispatcher
        self._handlers: dict[CommandType, CommandHandler] = {
            CommandType.STATUS: StatusHandler(),
            CommandType.INIT: InitHandler(),
            CommandType.RENDER: RenderHandler(),
            CommandType.RESET: ResetHandler(),
            CommandType.SHUTDOWN: ShutdownHandler(),
        }

        if bproc_mock or bpy_mock:
            bridge.inject_mocks(bproc_mock, bpy_mock)

        self.current_output_dir: Path | None = None
        self.writers: dict[str, Any] = {}

        try:
            if bridge.bproc:
                bridge.bproc.init()
                bridge.bproc.clean_up()
        except Exception:
            pass

    def get_telemetry(self) -> Telemetry:
        """Collects backend telemetry."""
        vram_used = 0.0
        vram_total = 0.0
        try:
            if GPUtil:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    vram_used = float(gpu.memoryUsed)
                    vram_total = float(gpu.memoryTotal)
        except Exception as e:
            logger.debug(f"Failed to collect GPU telemetry: {e}")

        return Telemetry(
            vram_used_mb=vram_used,
            vram_total_mb=vram_total,
            cpu_usage_percent=0.0,
            state_hash=calculate_state_hash(self.assets_loaded, self.parameters),
            uptime_seconds=time.time() - self.start_time,
        )

    def _setup_writers(self, output_dir: Path, shard_id: str = "main"):
        """Initializes or updates persistent writers."""
        if self.current_output_dir == output_dir:
            return

        self.current_output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        self.writers = {
            "csv": CSVWriter(output_dir / f"tags_shard_{shard_id}.csv"),
            "coco": COCOWriter(output_dir, filename=f"coco_shard_{shard_id}.json"),
            "rich": RichTruthWriter(output_dir / "rich_truth.json"),
            "sidecar": SidecarWriter(output_dir),
        }
        self.writers["csv"]._ensure_initialized()

    def handle_command(self, cmd: Command) -> Response:
        """Processes a single command using the Command Pattern dispatcher."""
        handler = self._handlers.get(cmd.command_type)
        if not handler:
            return Response(
                status=ResponseStatus.FAILURE,
                request_id=cmd.request_id,
                message=f"Command {cmd.command_type} not implemented",
            )

        try:
            return handler.handle(self, cmd)
        except Exception as e:
            logger.error(f"Error executing {cmd.command_type}: {e}", exc_info=True)
            return Response(
                status=ResponseStatus.FAILURE, request_id=cmd.request_id, message=str(e)
            )

    def run(self, max_renders: int | None = None):
        """Main server loop."""
        self.running = True
        self.max_renders = max_renders
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

                    if self.max_renders and self.renders_completed >= self.max_renders:
                        logger.info(f"Reached max_renders ({self.max_renders}). Shutting down.")
                        # Finalize immediately
                        self._finalize_writers()
                        time.sleep(1.0)
                        self.running = False

            except Exception as e:
                logger.error(f"Error in server loop: {e}")

        self._finalize_writers()

    def _finalize_writers(self):
        """Ensures all persistent data is saved."""
        if "coco" in self.writers:
            self.writers["coco"].save()
        if "rich" in self.writers:
            self.writers["rich"].save()

    def stop(self):
        self.running = False
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument(
        "--max-renders", type=int, default=None, help="Shutdown after N renders"
    )

    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args, unknown = parser.parse_known_args(argv)

    logger.info(f"Initializing ZmqBackendServer on port {args.port}")

    try:
        server = ZmqBackendServer(port=args.port)
        try:
            server.run(max_renders=args.max_renders)
        finally:
            server._finalize_writers()
    except KeyboardInterrupt:
        if "server" in locals():
            server.stop()
    except Exception as e:
        logger.exception(f"Server crashed: {e}")
        sys.exit(1)
