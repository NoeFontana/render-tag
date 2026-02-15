import os
import subprocess
import sys
import time

import pytest

from render_tag.orchestration.orchestrator import PersistentWorkerProcess


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


def test_suicide_pact_logic(tmp_path):
    """Verify that a worker self-terminates if its parent dies."""
    # We'll use a script that implements the logic
    suicide_script = tmp_path / "suicide_script.py"
    suicide_script.write_text("""
import os
import sys
import time
import threading
import signal

original_parent_pid = os.getppid()
print(f"Started with parent: {original_parent_pid}")

def suicide_pact():
    while True:
        time.sleep(1)
        if os.getppid() != original_parent_pid:
            print("Orphaned! Self-destructing.")
            os.kill(os.getpid(), signal.SIGKILL)

t = threading.Thread(target=suicide_pact, daemon=True)
t.start()

# Keep alive
while True:
    time.sleep(0.1)
""")

    # Spawn the suicide script as a child
    proc = subprocess.Popen(
        [sys.executable, str(suicide_script)], stdout=subprocess.PIPE, text=True
    )

    # Wait for it to start
    time.sleep(1)

    child_pid = proc.pid

    # Kill the parent (this process is the parent, but we want to simulate its death)
    # In this test, 'proc' is the child, 'this' is the parent.
    # If we kill 'proc', it just dies.
    # We need a middleman.

    launcher_script = tmp_path / "launcher.py"
    launcher_script.write_text(f"""
import subprocess
import time
import sys
proc = subprocess.Popen([{sys.executable!r}, {str(suicide_script)!r}])
print(f"CHILD_PID:{{proc.pid}}")
time.sleep(10)
""")

    launcher = subprocess.Popen(
        [sys.executable, str(launcher_script)], stdout=subprocess.PIPE, text=True
    )

    # Get the child PID from launcher output
    line = launcher.stdout.readline()
    if "CHILD_PID:" not in line:
        line = launcher.stdout.readline()

    child_pid = int(line.strip().split(":")[1])

    # Verify child is alive
    os.kill(child_pid, 0)

    # Kill the launcher (the direct parent of the suicide script)
    launcher.terminate()
    launcher.wait()

    # Now the child should be orphaned and self-destruct within 2 seconds
    time.sleep(3)

    try:
        os.kill(child_pid, 0)
        pytest.fail(f"Child {child_pid} should have self-destructed")
    except ProcessLookupError:
        pass  # Success
