import sys
import time

from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator


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
