import sys

from render_tag.orchestration import PersistentWorkerProcess


def test_memory_limit_injection(tmp_path):
    """Verify that memory_limit_mb is passed to the worker subprocess."""
    dummy_script = tmp_path / "memory_stub.py"
    dummy_script.write_text("""
import sys
import argparse
import zmq
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--memory-limit-mb", type=int)
    args, _ = parser.parse_known_args()

    # Log the received limit so the host can see it
    print(f"RECEIVED_LIMIT:{args.memory_limit_mb}")
    sys.stdout.flush()

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://127.0.0.1:{args.port}")

    while True:
        if socket.poll(100):
            msg = socket.recv_string()
            msg_json = json.loads(msg)
            response = {
                "status": "SUCCESS",
                "request_id": msg_json.get("request_id"),
                "data": {"status": "IDLE"}
            }
            socket.send_string(json.dumps(response))
""")

    worker = PersistentWorkerProcess(
        worker_id="mem-test",
        port=5570,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        memory_limit_mb=4096,
        startup_timeout=5
    )

    try:
        worker.start()
        # Check if the limit was logged by our stub
        logs = "\n".join(worker._startup_logs)
        assert "RECEIVED_LIMIT:4096" in logs
    finally:
        worker.stop()
