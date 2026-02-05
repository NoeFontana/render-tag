"""
Orchestrator for managing a pool of persistent Blender workers.
"""

import logging
import queue
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any

from render_tag.orchestration.persistent_worker import PersistentWorkerProcess
from render_tag.schema.hot_loop import CommandType, Response, ResponseStatus

logger = logging.getLogger(__name__)

class WorkerPool:
    """
    Manages a pool of persistent Blender worker processes.
    Provides a high-level API for task distribution and pool management.
    """

    def __init__(
        self,
        num_workers: int,
        base_port: int,
        blender_script: Path,
        blender_executable: str = "blenderproc",
        use_blenderproc: bool = True,
        mock: bool = False
    ):
        self.num_workers = num_workers
        self.base_port = base_port
        self.blender_script = blender_script
        self.blender_executable = blender_executable
        self.use_blenderproc = use_blenderproc
        self.mock = mock
        
        self.workers: List[PersistentWorkerProcess] = []
        self.worker_queue = queue.Queue()
        self._lock = threading.Lock()
        self.running = False

    def start(self):
        """Starts all workers in the pool."""
        with self._lock:
            if self.running:
                return
            
            logger.info(f"Starting WorkerPool with {self.num_workers} workers.")
            for i in range(self.num_workers):
                worker = PersistentWorkerProcess(
                    worker_id=f"worker-{i}",
                    port=self.base_port + i,
                    blender_script=self.blender_script,
                    blender_executable=self.blender_executable,
                    use_blenderproc=self.use_blenderproc,
                    mock=self.mock
                )
                worker.start()
                self.workers.append(worker)
                self.worker_queue.put(worker)
            
            self.running = True

    def stop(self):
        """Stops all workers in the pool."""
        with self._lock:
            if not self.running:
                return
            
            logger.info("Stopping WorkerPool.")
            for worker in self.workers:
                worker.stop()
            
            self.workers.clear()
            # Clear the queue
            while not self.worker_queue.empty():
                try:
                    self.worker_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.running = False

    def get_worker(self, timeout: Optional[float] = None) -> PersistentWorkerProcess:
        """Acquires a worker from the pool. Blocks until one is available."""
        return self.worker_queue.get(timeout=timeout)

    def release_worker(self, worker: PersistentWorkerProcess):
        """Returns a worker to the pool after use."""
        if not worker.is_healthy():
            logger.warning(f"Worker {worker.worker_id} is unhealthy. Restarting...")
            try:
                worker.stop()
                worker.start()
            except Exception as e:
                logger.error(f"Failed to restart worker {worker.worker_id}: {e}")
                # We still put it back or do we? 
                # If it failed to start, it's problematic. 
                # For now, let's keep trying to put it back so the pool doesn't shrink.
        
        self.worker_queue.put(worker)

    def execute_on_all(self, command_type: CommandType, payload: Optional[Dict[str, Any]] = None) -> List[Response]:
        """Executes a command on all workers in the pool (e.g., for INIT)."""
        responses = []
        # We don't use the queue here because we want to reach ALL specific workers
        for worker in self.workers:
            if worker.is_healthy():
                responses.append(worker.send_command(command_type, payload))
            else:
                responses.append(Response(
                    status=ResponseStatus.FAILURE,
                    request_id="pool-broadcast",
                    message=f"Worker {worker.worker_id} is unhealthy"
                ))
        return responses

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
