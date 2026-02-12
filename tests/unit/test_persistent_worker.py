import sys
from pathlib import Path

import pytest

from render_tag.orchestration.persistent_worker import PersistentWorkerProcess
from render_tag.schema.hot_loop import CommandType, ResponseStatus


def test_persistent_worker_lifecycle(tmp_path):
    # Create a dummy python script that acts as our "blender" backend
    # but uses a raw ZMQ stub to avoid importing project dependencies like blenderproc
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
                msg_json = json.loads(msg)
                
                # Minimal protocol implementation
                response = {
                    "status": "SUCCESS",
                    "message": "Stub success",
                    "request_id": msg_json.get("request_id"),
                    "data": {}
                }
                socket.send_string(json.dumps(response))
            except Exception as e:
                socket.send_string(json.dumps({"status": "FAILURE", "message": str(e)}))
""")

    # We use 'python' instead of 'blenderproc' for testing
    worker = PersistentWorkerProcess(
        worker_id="test-1",
        port=5559,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        startup_timeout=10,
        use_blenderproc=False,
    )

    try:
        worker.start()
        assert worker.is_healthy()

        resp = worker.send_command(CommandType.STATUS)
        assert resp.status == ResponseStatus.SUCCESS

        worker.stop()
        assert not worker.is_healthy()
        assert worker.process is None

    finally:
        worker.stop()


def test_persistent_worker_failure():
    # Invalid script
    worker = PersistentWorkerProcess(
        worker_id="fail-1",
        port=5560,
        blender_script=Path("non_existent.py"),
        blender_executable=sys.executable,
        startup_timeout=5,
        use_blenderproc=False,
    )

    with pytest.raises(RuntimeError):
        worker.start()
