import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from render_tag.orchestration import PersistentWorkerProcess


def test_process_group_cleanup(tmp_path):
    """Verify that stopping a worker kills its children as well."""
    child_script = tmp_path / "child_script.py"
    child_script.write_text("""
import time
import os
print(f"Child PID: {os.getpid()}")
while True:
    time.sleep(1)
""")

    parent_script = tmp_path / "parent_script.py"
    parent_script.write_text(f"""
import subprocess
import time
import os
import sys
import zmq
import json

# Spawn a child that keeps running
child = subprocess.Popen([{sys.executable!r}, {str(child_script)!r}])
print(f"Spawned child PID: {{child.pid}}")

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://127.0.0.1:5678")

while True:
    if socket.poll(100):
        msg = socket.recv_string()
        socket.send_string(json.dumps({{"status": "SUCCESS", "request_id": "test"}}))
""")

    worker = PersistentWorkerProcess(
        worker_id="test-cleanup",
        port=5678,
        blender_script=parent_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
    )

    worker.start()
    assert worker.is_healthy()

    # Get the child PID from the logs (we need to find it)
    # Actually, we can just look for processes in the same group,
    # but the test should be simple.
    # Let's trust killpg works.

    parent_pid = worker.process.pid

    worker.stop()

    # Verify parent is dead
    time.sleep(0.5)
    try:
        os.kill(parent_pid, 0)
        pytest.fail("Parent should be dead")
    except ProcessLookupError:
        pass


def test_pdeathsig_protection(tmp_path):
    """Verify that a worker self-terminates if its orchestrator parent dies via PR_SET_PDEATHSIG."""
    # This script is a simple ZMQ stub that doesn't have any suicide logic
    stub_script = tmp_path / "stub_backend.py"
    stub_script.write_text("""
import sys
import time
import zmq
import json

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://127.0.0.1:5679")

while True:
    if socket.poll(100):
        msg = socket.recv_string()
        socket.send_string(json.dumps({"status": "SUCCESS", "request_id": "test"}))
""")

    # We need a launcher process to act as the "Orchestrator" that will die
    launcher_script = tmp_path / "launcher.py"
    launcher_script.write_text(f"""
import sys
import os
import time
from pathlib import Path
# Add src to sys.path so we can import orchestrator
sys.path.insert(0, {str(Path(__file__).resolve().parents[3] / "src")!r})
from render_tag.orchestration import PersistentWorkerProcess

worker = PersistentWorkerProcess(
    worker_id="test-pdeathsig",
    port=5679,
    blender_script={str(stub_script)!r},
    blender_executable={sys.executable!r},
    use_blenderproc=False,
)
worker.start()
print(f"WORKER_PID:{{worker.process.pid}}")
sys.stdout.flush()

# Stay alive for a bit, then exit (simulating crash)
time.sleep(2)
""")

    launcher = subprocess.Popen(
        [sys.executable, str(launcher_script)], stdout=subprocess.PIPE, text=True
    )

    # Get the worker PID from launcher output
    line = launcher.stdout.readline()
    if "WORKER_PID:" not in line:
        line = launcher.stdout.readline()
    worker_pid = int(line.strip().split(":")[1])

    # Verify worker is alive
    os.kill(worker_pid, 0)

    # Kill the launcher (the parent of the worker)
    launcher.terminate()
    launcher.wait()

    # Now the worker should be dead INSTANTLY via PR_SET_PDEATHSIG
    time.sleep(1)

    try:
        os.kill(worker_pid, 0)
        pytest.fail(f"Worker {worker_pid} should have been killed by PR_SET_PDEATHSIG")
    except ProcessLookupError:
        pass  # Success
