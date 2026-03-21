
import threading
import time
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

    def __init__(self, ports: Optional[list[int]] = None):
        self.ports = ports or []
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
        except (ValidationError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse telemetry from {topic!r}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing telemetry: {e}")

    def _loop(self):
        """Internal ingestion loop."""
        logger.info(f"Health monitor ingestion loop started on ports: {self.ports}")
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        
        while self.running:
            try:
                # Poll with short timeout to allow checking self.running
                socks = dict(poller.poll(500))
                if self.socket in socks:
                    topic, payload = self.socket.recv_multipart()
                    self._process_message(topic, payload)
            except (zmq.ZMQError, zmq.ContextTerminated):
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")

    def start(self):
        """Starts the ingestion thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the ingestion thread and closes socket."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass

    def get_snapshot(self, worker_id: str) -> Optional[WorkerSnapshot]:
        """Returns the latest snapshot for a worker (Lock-Free Read)."""
        return self._registry.get(worker_id)

    def get_all_snapshots(self) -> Dict[str, WorkerSnapshot]:
        """Returns a copy of the current registry (Lock-Free Read)."""
        # Dictionary iteration is not strictly thread-safe in CPython if another 
        # thread is adding/removing keys, but dict.copy() or dict() is relatively safe.
        # Since we only add/update keys, and rarely remove, we'll return a copy.
        return self._registry.copy()
