import argparse
import json
import sys

import zmq

from render_tag.orchestration.worker_pool import WorkerPool


def test_vram_guardrail_restart(tmp_path):
    # Create a backend that reports HIGH VRAM
    dummy_script = tmp_path / "high_vram_backend.py"
    dummy_script.write_text("""
import sys
import argparse
import time
import zmq
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--mock", action="store_true")
    # Ignore other args
    parser.add_argument("--max-renders", type=int, default=None)
    args, _ = parser.parse_known_args()

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://127.0.0.1:{args.port}")

    print(f"Stub backend running on {args.port}")
    sys.stdout.flush()

    while True:
        if socket.poll(100):
            msg = socket.recv_string()
            request = json.loads(msg)
            
            # Respond with high VRAM in telemetry data
            response = {
                "status": "SUCCESS",
                "message": "High VRAM Stub",
                "request_id": request.get("request_id"),
                "data": {
                    # Telemetry matches schema expectations
                    "vram_used_mb": 5000.0,
                    "vram_total_mb": 8000.0,
                    "cpu_usage_percent": 10.0,
                    "state_hash": "dummy_hash",
                    "uptime_seconds": 100.0
                }
            }
            socket.send_string(json.dumps(response))
""")

    # Pool with 1000MB threshold
    with WorkerPool(
        num_workers=1,
        base_port=7100,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        vram_threshold_mb=1000.0,
    ) as pool:
        worker = pool.get_worker()
        original_pid = worker.process.pid

        # Releasing should trigger restart due to 5000MB > 1000MB
        pool.release_worker(worker)

        reborn = pool.get_worker()
        assert reborn.process.pid != original_pid
        assert reborn.is_healthy()
