
import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import zmq
from pydantic import ValidationError

from render_tag.core.logging import get_logger
from render_tag.core.schema.hot_loop import Telemetry, WorkerSnapshot

logger = get_logger(__name__)

class HealthMonitor:
    """
    Asynchronous health monitor for worker telemetry.
    
    Maintains a thread-safe registry of latest worker snapshots using
    atomic dictionary updates for lock-free reads.
    """

    def __init__(self, ports: Optional[list[int]] = None, log_path: Optional[Path] = None):
        self.ports = ports or []
        self.log_path = log_path
        self._registry: Dict[str, WorkerSnapshot] = {}
        self._lock = threading.Lock() # Only used for structural changes to the monitor itself
        
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.LINGER, 0)
        
        for port in self.ports:
            self.socket.connect(f"tcp://127.0.0.1:{port}")
        
        # Subscribe to all topics
        self.socket.subscribe(b"")

    def _persist_telemetry(self, worker_id: str, telemetry: Telemetry):
        """Writes telemetry to NDJSON log file."""
        if not self.log_path:
            return
            
        try:
            entry = {
                "timestamp": time.time(),
                "worker_id": worker_id,
                "telemetry": telemetry.model_dump()
            }
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist telemetry: {e}")

    def _process_message(self, topic: bytes, payload: bytes):
        """Processes a single telemetry message and updates the registry."""
        try:
            worker_id = topic.decode('utf-8')
            telemetry = Telemetry.model_validate_json(payload)
            
            snapshot = WorkerSnapshot(
                worker_id=worker_id,
                telemetry=telemetry,
                last_seen=time.time(),
                liveness="HEALTHY"
            )
            
            # Atomic dictionary update in CPython
            self._registry[worker_id] = snapshot
            
            # Persist to log file
            self._persist_telemetry(worker_id, telemetry)
        except (ValidationError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse telemetry from {topic!r}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing telemetry: {e}")

    def _check_liveness(self):
        """Sweeps the registry and flags unresponsive workers."""
        now = time.time()
        timeout = 10.0 # Heartbeat loss threshold
        
        # We need to iterate over a copy of keys to avoid modification during iteration
        for worker_id in list(self._registry.keys()):
            snapshot = self._registry.get(worker_id)
            if snapshot and snapshot.liveness == "HEALTHY":
                if now - snapshot.last_seen > timeout:
                    logger.warning(f"Worker {worker_id} heartbeat lost. Marking UNRESPONSIVE.")
                    # Update snapshot with new liveness
                    # snapshots are immutable (frozen=True), so we must create a new one
                    updated_snapshot = snapshot.model_copy(update={"liveness": "UNRESPONSIVE"})
                    self._registry[worker_id] = updated_snapshot

    def _loop(self):
        """Internal ingestion loop."""
        logger.info(f"Health monitor ingestion loop started on ports: {self.ports}")
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        
        last_sweep = time.time()
        
        while self.running:
            try:
                # Poll with short timeout to allow checking self.running
                socks = dict(poller.poll(500))
                if self.socket in socks:
                    topic, payload = self.socket.recv_multipart()
                    self._process_message(topic, payload)
                
                # Periodic liveness sweep (every 2 seconds)
                now = time.time()
                if now - last_sweep > 2.0:
                    self._check_liveness()
                    last_sweep = now
            except (zmq.ZMQError, zmq.ContextTerminated):
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")

    def start(self):
        """Starts the background ingestion and liveness sweep thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the ingestion thread and releases ZMQ resources."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass

    def get_snapshot(self, worker_id: str) -> Optional[WorkerSnapshot]:
        """Returns the latest health snapshot for a worker.
        
        This method is lock-free and provides zero-latency access to the latest state.
        
        Args:
            worker_id: The ID of the worker to interrogate.
            
        Returns:
            The WorkerSnapshot if found, else None.
        """
        return self._registry.get(worker_id)

    def get_all_snapshots(self) -> Dict[str, WorkerSnapshot]:
        """Returns a snapshot of the current registry.
        
        Returns:
            A dictionary mapping worker_id to its latest WorkerSnapshot.
        """
        # Create a copy using keys() list to avoid RuntimeError if the registry
        # changes size during iteration in CPython.
        return {k: self._registry[k] for k in list(self._registry.keys())}
