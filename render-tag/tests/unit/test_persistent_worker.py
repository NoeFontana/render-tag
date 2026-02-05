import pytest
import time
import sys
from pathlib import Path
from render_tag.orchestration.persistent_worker import PersistentWorkerProcess
from render_tag.schema.hot_loop import CommandType, ResponseStatus

def test_persistent_worker_lifecycle(tmp_path):
    # Create a dummy python script that acts as our "blender" backend
    project_root = Path(__file__).resolve().parents[3]
    src_path = project_root / "render-tag" / "src"
    dummy_script = tmp_path / "dummy_backend.py"
    dummy_script.write_text(f"""
import sys
import argparse
from pathlib import Path
# Add project root to path
sys.path.append(r'{src_path}')
from render_tag.backend.zmq_server import ZmqBackendServer

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    server = ZmqBackendServer(port=args.port)
    server.run()
""")
    # We use 'python' instead of 'blenderproc' for testing
    worker = PersistentWorkerProcess(
        worker_id="test-1",
        port=5559,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        startup_timeout=10,
        use_blenderproc=False
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
        use_blenderproc=False
    )
    
    with pytest.raises(RuntimeError):
        worker.start()