import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

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
    """ZeroMQ-based rendering server for Blender workers with Dual-Socket Architecture."""

    def __init__(
        self,
        port: int = 5555,
        shard_id: str = "main",
        seed: int = 42,
        job_spec: "JobSpec | None" = None,
        mgmt_port: int | None = None,
        memory_limit_mb: int | None = None,
        **mocks,
    ):
        self.port, self.shard_id, self.seed = port, shard_id, seed
        self.job_spec = job_spec
        self.mgmt_port = mgmt_port or (port + 100)
        self.memory_limit_mb = memory_limit_mb

        self.context = zmq.Context()

        # 1. Task Socket (REP) - Handles RENDER, INIT, SHUTDOWN
        self.task_socket = self.context.socket(zmq.REP)
        self.task_socket.setsockopt(zmq.LINGER, 0)
        self.task_socket.bind(f"tcp://127.0.0.1:{port}")

        # 2. Management Socket (REP) - Handles STATUS (Telemetry)
        self.mgmt_socket = self.context.socket(zmq.REP)
        self.mgmt_socket.setsockopt(zmq.LINGER, 0)
        self.mgmt_socket.bind(f"tcp://127.0.0.1:{self.mgmt_port}")

        # Ensure dependencies are stabilized for rendering
        bridge.stabilize(mocks.get("bproc_mock"), mocks.get("bpy_mock"), mocks.get("math_mock"))

        self.running = False
        self._lock = threading.Lock()

        # Shared State (Protected by self._lock)
        self.status = WorkerStatus.IDLE
        self.renders_completed = 0
        self.start_time = time.time()
        self.assets_loaded, self.parameters = [], {}
        self.current_output_dir, self.writers = None, {}
        self.bproc_initialized = False

    def _check_memory(self) -> bool:
        """Checks current memory usage and triggers shutdown if limit exceeded.
        
        Returns:
            True if memory is within limits, False if exceeded.
        """
        if self.memory_limit_mb is None:
            return True

        import gc
        import os

        import psutil

        # Trigger GC before final measurement to avoid premature restarts
        gc.collect()

        process = psutil.Process(os.getpid())
        current_usage_mb = process.memory_info().rss / (1024 * 1024)

        if current_usage_mb > self.memory_limit_mb:
            logger.warning(
                f"Memory limit exceeded: {current_usage_mb:.1f}MB > {self.memory_limit_mb}MB. "
                "Initiating preventative restart."
            )
            with self._lock:
                self.status = WorkerStatus.RESOURCE_LIMIT_EXCEEDED
            self.running = False
            return False

        return True

    def get_telemetry(self) -> Telemetry:
        """Returns current worker health and state metrics (Thread Safe)."""
        import os

        import psutil
        process = psutil.Process(os.getpid())
        
        with self._lock:
            return Telemetry(
                status=self.status,
                vram_used_mb=0.0,  # Placeholder for GPU VRAM
                vram_total_mb=0.0,
                cpu_usage_percent=process.cpu_percent(),
                state_hash=calculate_state_hash(self.assets_loaded, self.parameters),
                uptime_seconds=time.time() - self.start_time,
                ram_used_mb=process.memory_info().rss / (1024 * 1024),
            )

    def _setup_writers(self, output_dir: Path, shard_id: str):
        """Initialize data writers for the current shard."""
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
        """Flush and save data from active writers."""
        for w in self.writers.values():
            if hasattr(w, "save"):
                w.save()

    def stop(self):
        """Stops the server loop and closes sockets."""
        self.running = False
        try:
            self.task_socket.close(linger=0)
            self.mgmt_socket.close(linger=0)
            self.context.term()
        except Exception:
            pass

    def _mgmt_loop(self):
        """Dedicated thread for handling management requests (Heartbeats)."""
        logger.info(f"Management thread started on port {self.mgmt_port}")
        poller = zmq.Poller()
        poller.register(self.mgmt_socket, zmq.POLLIN)

        while self.running:
            try:
                # Periodic memory check
                if not self._check_memory():
                    break

                socks = dict(poller.poll(500))
                if self.mgmt_socket in socks:
                    msg = self.mgmt_socket.recv_string()
                    cmd = Command.model_validate_json(msg)

                    if cmd.command_type == CommandType.STATUS:
                        resp = self._on_status(cmd)
                        self.mgmt_socket.send_string(resp.model_dump_json())
                    else:
                        resp = Response(
                            status=ResponseStatus.FAILURE,
                            request_id=cmd.request_id,
                            message=f"Command {cmd.command_type} not supported on MGMT channel",
                        )
                        self.mgmt_socket.send_string(resp.model_dump_json())
            except (zmq.ZMQError, zmq.ContextTerminated):
                break
            except Exception as e:
                logger.error(f"MGMT loop error: {e}")

    def run(self, max_renders: int | None = None):
        """Starts the server loop."""
        self.running = True
        logger.info(f"Worker task server started on port {self.port}")

        # Start management thread
        mgmt_thread = threading.Thread(target=self._mgmt_loop, daemon=True)
        mgmt_thread.start()

        while self.running:
            try:
                # Periodic memory check
                if not self._check_memory():
                    break

                if not self.task_socket.poll(1000):
                    continue

                msg = self.task_socket.recv_string()
                cmd = Command.model_validate_json(msg)

                # Execute command (Blocks the task loop, but mgmt thread stays alive)
                resp = self._handle_command(cmd)

                with self._lock:
                    at_limit = max_renders and self.renders_completed >= max_renders
                    if at_limit:
                        self.status = WorkerStatus.FINISHED
                        self._finalize_writers()

                self.task_socket.send_string(resp.model_dump_json())

                if at_limit or cmd.command_type == CommandType.SHUTDOWN:
                    time.sleep(0.1)
                    self.running = False
            except (zmq.ZMQError, zmq.ContextTerminated):
                if not self.running:
                    break
                logger.error("ZMQ error in task loop", exc_info=True)
            except Exception as e:
                logger.error(f"Task loop error: {e}", exc_info=True)

        self._finalize_writers()

    def _handle_command(self, cmd: Command) -> Response:
        """Dispatch a command to the appropriate handler."""
        handlers = {
            CommandType.STATUS: self._on_status,
            CommandType.INIT: self._on_init,
            CommandType.RENDER: self._on_render,
            CommandType.RESET: self._on_reset,
            CommandType.SHUTDOWN: self._on_shutdown,
        }
        handler = handlers.get(cmd.command_type)
        if not handler:
            return Response(
                status=ResponseStatus.FAILURE, request_id=cmd.request_id, message="Unknown command"
            )

        try:
            return handler(cmd)
        except Exception as e:
            logger.exception(f"Command {cmd.command_type} failed: {e}")
            return Response(
                status=ResponseStatus.FAILURE, request_id=cmd.request_id, message=str(e)
            )

    def _on_status(self, cmd: Command) -> Response:
        """Handle STATUS command (Health check)."""
        return Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd.request_id,
            message="Alive",
            data=self.get_telemetry().model_dump(),
        )

    def _on_init(self, cmd: Command) -> Response:
        """Handle INIT command (Load assets/settings)."""
        with self._lock:
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
        """Handle RENDER command (Execute recipe)."""
        with self._lock:
            self.status = WorkerStatus.BUSY

        try:
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

            with self._lock:
                # Post-render memory check
                if not self._check_memory():
                    return Response(
                        status=ResponseStatus.FAILURE,
                        request_id=cmd.request_id,
                        message="RESOURCE_LIMIT_EXCEEDED: Memory limit exceeded after render.",
                    )

                self.renders_completed += 1
                self.status = WorkerStatus.IDLE

            return Response(
                status=ResponseStatus.SUCCESS,
                request_id=cmd.request_id,
                message=f"Rendered scene {scene_id}",
            )
        finally:
            with self._lock:
                if self.status == WorkerStatus.BUSY:
                    self.status = WorkerStatus.IDLE

    def _on_reset(self, cmd: Command) -> Response:
        """Handle RESET command (Clear scene)."""
        global_pool.release_all()
        return Response(status=ResponseStatus.SUCCESS, request_id=cmd.request_id, message="Reset")

    def _on_shutdown(self, cmd: Command) -> Response:
        """Handle SHUTDOWN command (Stop server)."""
        self.running = False
        return Response(
            status=ResponseStatus.SUCCESS, request_id=cmd.request_id, message="Shutdown"
        )
