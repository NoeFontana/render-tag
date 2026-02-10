import sys
import time
from pathlib import Path

from render_tag.orchestration.worker_pool import WorkerPool
from render_tag.schema.hot_loop import CommandType, ResponseStatus


def test_worker_pool_lifecycle(tmp_path):
    project_root = Path(__file__).resolve().parents[3]
    src_path = project_root / "render-tag" / "src"
    dummy_script = tmp_path / "dummy_backend.py"
    dummy_script.write_text(f"""
import sys
import argparse
from pathlib import Path
sys.path.append(r'{src_path}')
from render_tag.backend.zmq_server import ZmqBackendServer

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    server = ZmqBackendServer(port=args.port)
    server.run()
""")

    with WorkerPool(
        num_workers=2,
        base_port=5570,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
    ) as pool:
        assert len(pool.workers) == 2

        # Test broadcast
        responses = pool.execute_on_all(CommandType.STATUS)
        assert len(responses) == 2
        for r in responses:
            assert r.status == ResponseStatus.SUCCESS

        # Test queue access
        w1 = pool.get_worker()
        w2 = pool.get_worker()
        assert w1.worker_id != w2.worker_id

        pool.release_worker(w1)
        pool.release_worker(w2)


def test_worker_pool_resilience(tmp_path):
    project_root = Path(__file__).resolve().parents[3]
    src_path = project_root / "render-tag" / "src"
    dummy_script = tmp_path / "dummy_backend.py"
    dummy_script.write_text(f"""
import sys
import argparse
from pathlib import Path
sys.path.append(r'{src_path}')
from render_tag.backend.zmq_server import ZmqBackendServer

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    server = ZmqBackendServer(port=args.port)
    server.run()
""")

    with WorkerPool(
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
