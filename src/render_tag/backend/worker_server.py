import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import zmq

from render_tag.backend.assets import global_pool
from render_tag.backend.bridge import bridge
from render_tag.backend.engine import RenderContext, execute_recipe
from render_tag.backend.scene import setup_background
from render_tag.core.logging import get_logger
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

if TYPE_CHECKING:
    from render_tag.core.schema.job import JobSpec

logger = get_logger(__name__)


class ZmqBackendServer:
    """ZeroMQ-based rendering server for Blender workers."""

    def __init__(
        self,
        port: int = 5555,
        shard_id: str = "main",
        seed: int = 42,
        job_spec: "JobSpec | None" = None,
        **mocks,
    ):
        self.port, self.shard_id, self.seed = port, shard_id, seed
        self.job_spec = job_spec
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://127.0.0.1:{port}")
        
        bridge.stabilize(mocks.get("bproc_mock"), mocks.get("bpy_mock"), mocks.get("math_mock"))

        self.running = False
        self.status = WorkerStatus.IDLE
        self.renders_completed = 0
        self.start_time = time.time()
        self.assets_loaded, self.parameters = [], {}
        self.current_output_dir, self.writers = None, {}
        self.bproc_initialized = False

    def get_telemetry(self) -> Telemetry:
        """Returns current worker health and state metrics."""
        return Telemetry(
            status=self.status,
            vram_used_mb=0.0,  # Placeholder
            vram_total_mb=0.0,
            cpu_usage_percent=0.0,
            state_hash=calculate_state_hash(self.assets_loaded, self.parameters),
            uptime_seconds=time.time() - self.start_time,
        )

    def _setup_writers(self, output_dir: Path, shard_id: str):
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

    def _finalize_writers(self):
        for w in self.writers.values():
            if hasattr(w, "save"):
                w.save()

    def stop(self):
        """Stops the server loop and closes sockets."""
        self.running = False
        try:
            self.socket.close(linger=0)
            self.context.term()
        except Exception:
            pass

    def run(self, max_renders: int | None = None):
        """Starts the server loop."""
        self.running = True
        logger.info(f"Worker server started on port {self.port}")
        while self.running:
            try:
                if not self.socket.poll(1000):
                    continue
                
                msg = self.socket.recv_string()
                cmd = Command.model_validate_json(msg)
                resp = self._handle_command(cmd)
                
                at_limit = max_renders and self.renders_completed >= max_renders
                if at_limit:
                    self.status = WorkerStatus.FINISHED
                    self._finalize_writers()
                
                self.socket.send_string(resp.model_dump_json())
                if at_limit:
                    time.sleep(0.1)
                    self.running = False
            except (zmq.ZMQError, zmq.ContextTerminated):
                if not self.running:
                    break
                logger.error("ZMQ error in server loop", exc_info=True)
            except Exception as e:
                logger.error(f"Server loop error: {e}", exc_info=True)

        self._finalize_writers()

    def _handle_command(self, cmd: Command) -> Response:
        handlers = {
            CommandType.STATUS: self._on_status,
            CommandType.INIT: self._on_init,
            CommandType.RENDER: self._on_render,
            CommandType.RESET: self._on_reset,
            CommandType.SHUTDOWN: self._on_shutdown,
        }
        handler = handlers.get(cmd.command_type)
        if not handler:
            return Response(status=ResponseStatus.FAILURE, request_id=cmd.request_id, message="Unknown command")
        
        try:
            return handler(cmd)
        except Exception as e:
            logger.exception(f"Command {cmd.command_type} failed: {e}")
            return Response(status=ResponseStatus.FAILURE, request_id=cmd.request_id, message=str(e))

    def _on_status(self, cmd: Command) -> Response:
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message="Alive",
            data=self.get_telemetry().model_dump(),
        )

    def _on_init(self, cmd: Command) -> Response:
        if not self.bproc_initialized and bridge.bproc:
            bridge.bproc.init()
            bridge.bproc.clean_up()
            self.bproc_initialized = True

        payload = cmd.payload or {}
        for path in payload.get("assets", []):
            if path not in self.assets_loaded:
                p = Path(path)
                if p.exists() and p.suffix.lower() in [".exr", ".hdr"] and bridge.bpy:
                    setup_background(p)
                self.assets_loaded.append(path)
        self.parameters.update(payload.get("parameters", {}))
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message=f"{len(self.assets_loaded)} assets resident",
        )

    def _on_render(self, cmd: Command) -> Response:
        self.status = WorkerStatus.BUSY
        p = cmd.payload or {}
        recipe, output_dir = p.get("recipe"), Path(p.get("output_dir", "."))
        shard_id = p.get("shard_id", self.shard_id)
        
        self._setup_writers(output_dir, shard_id)
        scene_id = recipe.get("scene_id", 0)
        render_seed = derive_seed(self.seed, "render", scene_id)
        
        ctx = RenderContext(
            output_dir=output_dir,
            renderer_mode=p.get("renderer_mode", "cycles"),
            csv_writer=self.writers["csv"],
            coco_writer=self.writers["coco"],
            rich_writer=self.writers["rich"],
            sidecar_writer=self.writers["sidecar"],
            global_seed=self.seed,
            skip_visibility=p.get("skip_visibility", False),
        )
        
        execute_recipe(recipe, ctx=ctx, seed=render_seed)
        self.renders_completed += 1
        self.status = WorkerStatus.IDLE
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message=f"Rendered scene {scene_id}",
        )

    def _on_reset(self, cmd: Command) -> Response:
        global_pool.release_all()
        return Response(status=ResponseStatus.SUCCESS, request_id=cmd.request_id, message="Reset")

    def _on_shutdown(self, cmd: Command) -> Response:
        self.running = False
        return Response(status=ResponseStatus.SUCCESS, request_id=cmd.request_id, message="Shutdown")
