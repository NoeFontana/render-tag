import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from render_tag.core.schema.job import JobSpec

import zmq

from render_tag.backend.assets import global_pool
from render_tag.backend.bridge import bridge
from render_tag.backend.engine import RenderContext, execute_recipe
from render_tag.backend.scene import setup_background
from render_tag.core.schema.hot_loop import (
    Command,
    CommandType,
    Response,
    ResponseStatus,
    Telemetry,
    WorkerStatus,
    calculate_state_hash,
)
from render_tag.core.seeding import derive_seed
from render_tag.data_io.writers import (
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)

try:
    import GPUtil
except ImportError:
    GPUtil = None

logger = logging.getLogger(__name__)


class ZmqBackendServer:
    def __init__(
        self,
        port: int = 5555,
        shard_id: str = "main",
        bproc_mock=None,
        bpy_mock=None,
        seed: int = 42,
        logger: logging.Logger | None = None,
        job_spec: "JobSpec | None" = None,
    ):
        self.port = port
        self.shard_id = shard_id
        self.seed = seed
        self.job_spec = job_spec
        self.logger = logger or logging.getLogger(__name__)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://127.0.0.1:{port}")
        self.running = False
        self.assets_loaded, self.parameters = [], {}
        self.start_time = time.time()
        self.renders_completed = 0
        self.status = WorkerStatus.IDLE
        self._handlers = {
            CommandType.STATUS: StatusHandler(),
            CommandType.INIT: InitHandler(),
            CommandType.RENDER: RenderHandler(),
            CommandType.RESET: ResetHandler(),
            CommandType.SHUTDOWN: ShutdownHandler(),
        }
        if bproc_mock or bpy_mock:
            bridge.stabilize(bproc_mock, bpy_mock)
        else:
            bridge.stabilize()

        self.current_output_dir, self.writers = None, {}
        self.bproc_initialized = False
        self.writers_finalized = False

    def get_telemetry(self) -> Telemetry:
        # Staff Engineer: Temporarily bypass GPUtil to diagnose potential driver hangs
        vram_used, vram_total = 0.0, 0.0
        return Telemetry(
            status=self.status,
            vram_used_mb=vram_used,
            vram_total_mb=vram_total,
            cpu_usage_percent=0.0,
            state_hash=calculate_state_hash(self.assets_loaded, self.parameters),
            uptime_seconds=time.time() - self.start_time,
        )

    def _setup_writers(self, output_dir: Path, shard_id: str | None = None):
        if shard_id is None or shard_id == "main":
            shard_id = self.shard_id

        if self.current_output_dir == output_dir:
            return
        self.current_output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        self.writers = {
            "csv": CSVWriter(output_dir / f"tags_shard_{shard_id}.csv"),
            "coco": COCOWriter(output_dir, filename=f"coco_shard_{shard_id}.json"),
            "rich": RichTruthWriter(output_dir / f"rich_truth_shard_{shard_id}.json"),
            "sidecar": SidecarWriter(output_dir),
        }
        self.writers["csv"]._ensure_initialized()

    def handle_command(self, cmd: Command) -> Response:
        handler = self._handlers.get(cmd.command_type)
        if not handler:
            return Response(
                status=ResponseStatus.FAILURE, request_id=cmd.request_id, message="Not implemented"
            )
        try:
            self.logger.debug(f"Handling command: {cmd.command_type}")
            return handler.handle(self, cmd)
        except Exception as e:
            self.logger.error(f"Error handling {cmd.command_type}: {e}", exc_info=True)
            return Response(
                status=ResponseStatus.FAILURE, request_id=cmd.request_id, message=str(e)
            )

    def run(self, max_renders: int | None = None):
        self.running, self.max_renders = True, max_renders
        self.logger.info(f"Entering ZMQ server loop (port={self.port})")
        while self.running:
            try:
                if self.socket.poll(1000):
                    message = self.socket.recv_string()
                    self.logger.debug(f"Received msg: {message[:100]}...")
                    cmd = Command.model_validate_json(message)
                    resp = self.handle_command(cmd)

                    # Staff Engineer: If this was the final render, finalize BEFORE replying.
                    # This ensures the orchestrator doesn't start a replacement worker
                    # until this one has finished all disk I/O and released file locks.
                    at_limit = self.max_renders and self.renders_completed >= self.max_renders
                    if at_limit:
                        self.logger.info(f"Reached max renders ({self.max_renders}). Finalizing...")
                        self.status = WorkerStatus.FINISHED
                        self._finalize_writers()

                    self.socket.send_string(resp.model_dump_json())

                    if at_limit:
                        # Graceful exit
                        time.sleep(0.1)
                        self.running = False
                else:
                    # Staff Engineer: Heartbeat logging
                    self.logger.debug("Worker idle, waiting for command...")
            except Exception as e:
                self.logger.error(f"Error in server loop: {e}")
        self._finalize_writers()

    def _finalize_writers(self):
        if getattr(self, "writers_finalized", False):
            return
        if "coco" in self.writers:
            self.writers["coco"].save()
        if "rich" in self.writers:
            self.writers["rich"].save()
        self.writers_finalized = True

    def stop(self):
        self.running = False
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass


class CommandHandler(Protocol):
    def handle(self, server: "ZmqBackendServer", cmd: Command) -> Response: ...


class StatusHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message="Alive",
            data=server.get_telemetry().model_dump(),
        )


class InitHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        # Staff Engineer: Initialize bproc here to avoid startup timeouts
        if not server.bproc_initialized:
            try:
                if bridge.bproc:
                    bridge.bproc.init()
                    bridge.bproc.clean_up()
                server.bproc_initialized = True
            except Exception as e:
                server.logger.error(f"BlenderProc initialization failed: {e}")
                return Response(
                    status=ResponseStatus.FAILURE,
                    request_id=cmd.request_id,
                    message=f"BProc Init Failed: {e}",
                )

        payload = cmd.payload or {}
        assets, parameters = payload.get("assets", []), payload.get("parameters", {})
        for asset_path in assets:
            if asset_path not in server.assets_loaded:
                p = Path(asset_path)
                if p.exists() and p.suffix.lower() in [".exr", ".hdr"] and bridge.bpy:
                    setup_background(p)
                server.assets_loaded.append(asset_path)
        server.parameters.update(parameters)
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message=f"Initialized. {len(server.assets_loaded)} assets resident.",
            data={"state_hash": calculate_state_hash(server.assets_loaded, server.parameters)},
        )


class RenderHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        server.status = WorkerStatus.BUSY
        payload = cmd.payload or {}
        recipe, output_dir = payload.get("recipe"), payload.get("output_dir")
        renderer_mode, shard_id = (
            payload.get("renderer_mode", "cycles"),
            payload.get("shard_id", "main"),
        )
        if not recipe or not output_dir:
            return Response(
                status=ResponseStatus.FAILURE, request_id=cmd.request_id, message="Missing payload"
            )
        server._setup_writers(Path(output_dir), shard_id=shard_id)

        # Derive deterministic seed for this specific render task
        # We use the global worker seed + "render" domain + scene_id
        scene_id = recipe.get("scene_id", 0)
        render_seed = derive_seed(server.seed, "render", scene_id)

        # Construct and use RenderContext
        ctx = RenderContext(
            output_dir=Path(output_dir),
            renderer_mode=renderer_mode,
            csv_writer=server.writers["csv"],
            coco_writer=server.writers["coco"],
            rich_writer=server.writers["rich"],
            sidecar_writer=server.writers["sidecar"],
            global_seed=server.seed,
            logger=server.logger,
            skip_visibility=payload.get("skip_visibility", False),
        )

        execute_recipe(
            recipe,
            ctx=ctx,
            seed=render_seed,
        )
        server.renders_completed += 1
        server.status = WorkerStatus.IDLE
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
            message="Reset",
            data={"state_hash": calculate_state_hash(server.assets_loaded, server.parameters)},
        )


class ShutdownHandler:
    def handle(self, server: ZmqBackendServer, cmd: Command) -> Response:
        server.running = False
        return Response(
            status=ResponseStatus.SUCCESS, request_id=cmd.request_id, message="Shutdown"
        )
