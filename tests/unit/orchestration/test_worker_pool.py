import sys
import time

from render_tag.orchestration import UnifiedWorkerOrchestrator


def test_worker_pool_lifecycle(tmp_path):
    dummy_script = tmp_path / "dummy_backend.py"
    dummy_script.write_text("""
import sys
import argparse
import time
import zmq
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    # Accept but ignore other args that persistent_worker passes
    parser.add_argument("--mock", action="store_true")
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
            try:
                # Basic protocol response
                request = json.loads(msg)
                command_type = request.get("command_type")
                
                response = {
                    "status": "SUCCESS",
                    "message": "Stub success",
                    "request_id": request.get("request_id"),
                    "data": {
                        "vram_used_mb": 100,
                        "vram_total_mb": 8000,
                        "cpu_usage_percent": 10,
                        "state_hash": "abc",
                        "uptime_seconds": 10
                    }
                }
                socket.send_string(json.dumps(response))
            except Exception as e:
                # Fallback error
                socket.send_string(json.dumps({"status": "FAILURE", "message": str(e)}))
""")

    with UnifiedWorkerOrchestrator(
        num_workers=2,
        base_port=5570,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
    ) as pool:
        assert len(pool.workers) == 2

        # Test queue access
        w1 = pool.get_worker()
        w2 = pool.get_worker()
        assert w1.worker_id != w2.worker_id

        pool.release_worker(w1)
        pool.release_worker(w2)


def test_worker_pool_resilience(tmp_path):
    dummy_script = tmp_path / "dummy_backend.py"
    dummy_script.write_text("""
import sys
import argparse
import time
import zmq
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    # Accept but ignore other args that persistent_worker passes
    parser.add_argument("--mock", action="store_true")
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
            response = {
                "status": "SUCCESS",
                "message": "Stub success",
                "request_id": request.get("request_id"),
                "data": {
                    "vram_used_mb": 100,
                    "vram_total_mb": 8000,
                    "cpu_usage_percent": 10,
                    "state_hash": "abc",
                    "uptime_seconds": 10
                }
            }
            socket.send_string(json.dumps(response))
""")

    with UnifiedWorkerOrchestrator(
        num_workers=1,
        base_port=5580,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
    ) as pool:
        worker = pool.get_worker()
        assert worker.is_healthy()

        # Kill the process manually
        worker.process.kill()
        time.sleep(0.1)
        assert not worker.is_healthy()

        # Releasing should trigger restart
        pool.release_worker(worker)

        # Get it back and check health
        worker_reborn = pool.get_worker()
        assert worker_reborn.is_healthy()
        assert worker_reborn.worker_id == "worker-0"


def test_worker_throttling_env(tmp_path):
    """Verify that OMP_NUM_THREADS is correctly injected."""
    dummy_script = tmp_path / "env_check.py"
    dummy_script.write_text("""
import sys
import os
import argparse
import zmq
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    args, _ = parser.parse_known_args()

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://127.0.0.1:{args.port}")

    while True:
        if socket.poll(100):
            msg = socket.recv_string()
            request = json.loads(msg)
            
            # Send back the environment variables we care about
            response = {
                "status": "SUCCESS",
                "message": "Env check",
                "request_id": request.get("request_id"),
                "data": {
                    "vram_used_mb": 0,
                    "vram_total_mb": 0,
                    "cpu_usage_percent": 0,
                    "state_hash": os.environ.get("OMP_NUM_THREADS", "not set"),
                    "uptime_seconds": int(os.environ.get("BLENDER_CPU_THREADS", "0"))
                }
            }
            socket.send_string(json.dumps(response))
""")

    # Force a known cpu count for predictable test
    from unittest.mock import patch

    with (
        patch("os.cpu_count", return_value=16),
        UnifiedWorkerOrchestrator(
            num_workers=2,
            base_port=5590,
            blender_script=dummy_script,
            blender_executable=sys.executable,
            use_blenderproc=False,
        ) as pool,
    ):
        # (16 - 2) / 2 = 7
        assert pool.thread_budget == 7
        worker = pool.get_worker()

        # Use STATUS command which we've hijacked to return env info in our dummy script
        resp = worker.send_command("STATUS")
        assert resp.data["state_hash"] == "7"
        assert resp.data["uptime_seconds"] == 7
