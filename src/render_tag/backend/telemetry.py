
import os
import threading
import time
from pathlib import Path
from typing import Any

import psutil
import zmq

from render_tag.backend.bridge import bridge
from render_tag.core.logging import get_logger
from render_tag.core.schema.hot_loop import Telemetry, calculate_state_hash

logger = get_logger(__name__)

class TelemetryEmitter:
    """Asynchronous telemetry emitter for Blender workers using ZMQ PUB/SUB."""

    def __init__(
        self,
        worker_id: str,
        port: int,
        interval_ms: int = 1000,
        server_ref: Any = None
    ):
        """Initializes the telemetry emitter.
        
        Args:
            worker_id: Unique identifier for the worker.
            port: ZMQ PUB port to bind to.
            interval_ms: Milliseconds between heartbeat emissions.
            server_ref: Optional reference to ZmqBackendServer for metrics.
        """
        self.worker_id = worker_id
        self.port = port
        self.interval_s = interval_ms / 1000.0
        self.server = server_ref # Reference to ZmqBackendServer for status/assets
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind(f"tcp://127.0.0.1:{self.port}")
        
        self.running = False
        self._thread = None

    def poll_metrics(self) -> Telemetry:
        """Collects system and Blender-specific metrics.
        
        Returns:
            Current Telemetry snapshot.
        """
        if self.server:
            return self.server.get_telemetry()

        # Fallback if no server reference (e.g. standalone tests)
        process = psutil.Process(os.getpid())
        
        return Telemetry(
            status="IDLE",
            vram_used_mb=0.0,
            vram_total_mb=0.0,
            ram_used_mb=process.memory_info().rss / (1024 * 1024),
            cpu_usage_percent=process.cpu_percent(),
            state_hash="standalone",
            uptime_seconds=0.0,
            object_count=0,
            active_scene_id=None
        )

    def _loop(self):
        """Internal emission loop."""
        logger.info(f"Telemetry emitter started for {self.worker_id} on port {self.port}")
        while self.running:
            try:
                telemetry = self.poll_metrics()
                # Topic tagging: "worker_id payload"
                topic = self.worker_id.encode('utf-8')
                payload = telemetry.model_dump_json().encode('utf-8')
                self.socket.send_multipart([topic, payload])
            except Exception as e:
                logger.error(f"Telemetry emission error: {e}")
            
            time.sleep(self.interval_s)

    def start(self):
        """Starts the emission thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the emission thread and closes socket."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass
