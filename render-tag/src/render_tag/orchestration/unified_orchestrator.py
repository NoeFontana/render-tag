"""
Unified orchestration logic for managing both ephemeral and persistent Blender workers.
"""

import logging
import queue
import sys
import threading
from pathlib import Path
from typing import Any, ClassVar

import zmq

from render_tag.orchestration.persistent_worker import PersistentWorkerProcess
from render_tag.schema.hot_loop import CommandType, Response, ResponseStatus
from render_tag.tools.telemetry_auditor import TelemetryAuditor

logger = logging.getLogger(__name__)

class UnifiedWorkerOrchestrator:
    """
    Manages a pool of workers that can be either persistent or ephemeral.
    Standardizes the rendering execution across all 프로젝트 flows.
    """
    
    _instances: ClassVar[list['UnifiedWorkerOrchestrator']] = []

    def __init__(
        self,
        num_workers: int,
        base_port: int,
        blender_script: Path | None = None,
        blender_executable: str | None = None,
        use_blenderproc: bool = True,
        mock: bool = False,
        vram_threshold_mb: float | None = None,
        ephemeral: bool = False,
        max_renders_per_worker: int | None = None
    ):
        self.num_workers = num_workers
        self.base_port = base_port
        
        # Default to standard zmq_server if no script provided
        if blender_script is None:
            blender_script = Path(__file__).resolve().parents[1] / "backend" / "zmq_server.py"
            
        self.blender_script = blender_script
        
        # In mock mode, we usually want to run with standard python unless explicitly told otherwise
        if blender_executable is None:
            if mock:
                self.blender_executable = sys.executable
                use_blenderproc = False
            else:
                self.blender_executable = "blenderproc"
        else:
            self.blender_executable = blender_executable

        self.use_blenderproc = use_blenderproc
        self.mock = mock
        self.vram_threshold_mb = vram_threshold_mb
        self.ephemeral = ephemeral
        self.max_renders_per_worker = max_renders_per_worker
        
        self.context = zmq.Context()
        self.workers: list[PersistentWorkerProcess] = []
        self.worker_queue = queue.Queue()
        self.auditor = TelemetryAuditor()
        self._lock = threading.Lock()
        self.running = False
        
        UnifiedWorkerOrchestrator._instances.append(self)

    @classmethod
    def cleanup_all(cls):
        """Global cleanup for all active orchestrators."""
        for instance in list(cls._instances):
            instance.stop()
        cls._instances.clear()

    def start(self):
        """Starts the worker pool."""
        with self._lock:
            if self.running:
                return
            
            logger.info(
                f"Starting UnifiedWorkerOrchestrator with {self.num_workers} workers "
                f"(ephemeral={self.ephemeral})."
            )
            for i in range(self.num_workers):
                worker = PersistentWorkerProcess(
                    worker_id=f"worker-{i}",
                    port=self.base_port + i,
                    blender_script=self.blender_script,
                    blender_executable=self.blender_executable,
                    use_blenderproc=self.use_blenderproc,
                    mock=self.mock,
                    max_renders=self.max_renders_per_worker,
                    context=self.context
                )
                
                worker.start()
                self.workers.append(worker)
                self.worker_queue.put(worker)
            
            self.running = True

    def stop(self):
        """Stops all workers and saves telemetry."""
        with self._lock:
            if not self.running:
                return
            
            logger.info("Stopping UnifiedWorkerOrchestrator.")
            for worker in self.workers:
                worker.stop()
            
            self.workers.clear()
            while not self.worker_queue.empty():
                try:
                    self.worker_queue.get_nowait()
                except queue.Empty:
                    break
            
            # self.context.term() # Removed to avoid hangs
            self.running = False

    def get_worker(self, timeout: float | None = None) -> PersistentWorkerProcess:
        """Acquires a worker."""
        return self.worker_queue.get(timeout=timeout)

    def release_worker(self, worker: PersistentWorkerProcess):
        """Returns a worker, handling restarts for health or VRAM."""
        should_restart = False
        
        # 1. Always record a baseline activity entry to ensure auditor is not empty
        # We use a dummy telemetry if we can't get real one
        from render_tag.schema.hot_loop import Telemetry
        baseline_tel = Telemetry(
            vram_used_mb=0, 
            vram_total_mb=0, 
            cpu_usage_percent=0, 
            state_hash="unknown", 
            uptime_seconds=0
        )
        
        # 2. Check health and collect real telemetry
        is_healthy = False
        try:
            if worker.client:
                # Use a very short timeout for quick health check
                worker.client.socket.setsockopt(zmq.RCVTIMEO, 1000)
                resp = worker.send_command(CommandType.STATUS)
                if resp.status == ResponseStatus.SUCCESS:
                    is_healthy = True
                    real_tel = Telemetry(**resp.data)
                    self.auditor.add_entry(worker.worker_id, real_tel, event_type="render_complete")
                    
                    if self.vram_threshold_mb and real_tel.vram_used_mb > self.vram_threshold_mb:
                        logger.warning(f"Worker {worker.worker_id} exceeded VRAM threshold.")
                        should_restart = True
                
                # Restore timeout
                worker.client.socket.setsockopt(zmq.RCVTIMEO, 10000)
        except Exception as e:
            logger.debug(f"Telemetry/Health check failed during release: {e}")
            is_healthy = False

        if not is_healthy:
            should_restart = True
            # Add the baseline entry if we couldn't get a real one
            self.auditor.add_entry(
                worker.worker_id, baseline_tel, event_type="render_complete_fallback"
            )

        if should_restart and self.running:
            if self.ephemeral:
                logger.debug(f"Ephemeral worker {worker.worker_id} finished. Restarting...")
            else:
                logger.info(f"Restarting worker {worker.worker_id}...")
            try:
                worker.stop()
                worker.start()
            except Exception as e:
                logger.error(f"Failed to restart {worker.worker_id}: {e}")
        
        self.worker_queue.put(worker)

    def execute_recipe(
        self, 
        recipe: dict[str, Any], 
        output_dir: Path, 
        renderer_mode: str = "cycles",
        shard_id: str = "main"
    ) -> Response:
        """Helper to execute a single recipe using an available worker."""
        worker = self.get_worker()
        try:
            resp = worker.send_command(
                CommandType.RENDER,
                payload={
                    "recipe": recipe,
                    "output_dir": str(output_dir),
                    "renderer_mode": renderer_mode,
                    "shard_id": shard_id,
                    "skip_visibility": self.mock # Auto-skip visibility in mock mode
                }
            )
            return resp
        finally:
            self.release_worker(worker)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
