import sys
import time

from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator


def test_vram_guardrail_restart(tmp_path):
    """Verify that a worker is restarted if it exceeds VRAM threshold."""
    # 1. Create a dummy backend that reports high VRAM usage on STATUS
    dummy_script = tmp_path / "vram_backend.py"
    dummy_script.write_text("""
import sys
import argparse
import zmq
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    args, _ = parser.parse_known_args()

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://127.0.0.1:{args.port}")

    while True:
        msg = socket.recv_string()
        request = json.loads(msg)
        
        # Handle SHUTDOWN to allow process termination
        if request.get("command_type") == "SHUTDOWN":
            response = {
                "status": "SUCCESS",
                "message": "Bye",
                "request_id": request.get("request_id"),
            }
            socket.send_string(json.dumps(response))
            break

        # Always report high VRAM
        response = {
            "status": "SUCCESS",
            "message": "VRAM heavy",
            "request_id": request.get("request_id"),
            "data": {
                "vram_used_mb": 2000,
                "vram_total_mb": 8000,
                "cpu_usage_percent": 50,
                "state_hash": "busy",
                "uptime_seconds": 100
            }
        }
        socket.send_string(json.dumps(response))
""")

    # 2. Start pool with low threshold (1000 MB)
    with UnifiedWorkerOrchestrator(
        num_workers=1,
        base_port=5650,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        mock=True,
        vram_threshold_mb=1000,
    ) as pool:
        worker = pool.get_worker()
        original_pid = worker.process.pid

        # 3. Releasing should trigger VRAM check -> STATUS command -> High VRAM -> Restart
        pool.release_worker(worker)

        # Wait for restart
        time.sleep(0.5)

        # 4. Get worker again and check PID
        worker_new = pool.get_worker()
        assert worker_new.process.pid != original_pid
