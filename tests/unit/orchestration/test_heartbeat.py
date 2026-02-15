import threading
import time
from pathlib import Path

import pytest

from render_tag.backend.worker_server import ZmqBackendServer
from render_tag.core.schema.hot_loop import CommandType, ResponseStatus, WorkerStatus
from render_tag.orchestration.client import ZmqHostClient


def test_heartbeat_prevents_timeout():
    """
    Test that the host client does not timeout during a long render if heartbeats are alive.
    """
    port = 29900
    mgmt_port = 30000

    # 1. Setup a worker that "sleeps" during render to simulate a long task
    class SlowWorker(ZmqBackendServer):
        def _on_render(self, cmd):
            self.status = WorkerStatus.BUSY
            # Sleep longer than the heartbeat interval but shorter than the global safety valve
            # We'll use a short timeout for the test to make it fast
            time.sleep(5)
            self.status = WorkerStatus.IDLE
            return super()._on_render(cmd)

    worker = SlowWorker(port=port, mgmt_port=mgmt_port, mock=True)
    worker_thread = threading.Thread(target=worker.run, daemon=True)
    worker_thread.start()

    time.sleep(1)  # Wait for startup

    try:
        # 2. Setup a client with a SHORTER timeout than the render,
        # but a VERY SHORT heartbeat interval so it resets the timer.
        client = ZmqHostClient(
            port=port,
            mgmt_port=mgmt_port,
            timeout_ms=3000,  # 3s timeout
            heartbeat_interval_s=1.0,  # 1s heartbeat
        )

        start = time.time()
        # The render takes 5s, but timeout is 3s.
        # Heartbeats every 1s should allow it to pass.
        resp = client.send_command(
            CommandType.RENDER,
            payload={
                "recipe": {
                    "scene_id": 1,
                    "cameras": [
                        {
                            "intrinsics": {"resolution": [1920, 1080], "fov": 70.0},
                            "transform_matrix": [
                                [1, 0, 0, 0],
                                [0, 1, 0, 0],
                                [0, 0, 1, 0],
                                [0, 0, 0, 1],
                            ],
                        }
                    ],
                    "objects": [],
                },
                "output_dir": ".",
            },
        )
        duration = time.time() - start

        assert resp.status == ResponseStatus.SUCCESS
        assert duration >= 5.0
        print(f"RESILIENCE SUCCESS: Render completed in {duration:.2f}s (Timeout was 3s)")

    finally:
        worker.stop()
        worker_thread.join(timeout=2)


if __name__ == "__main__":
    test_heartbeat_prevents_timeout()
