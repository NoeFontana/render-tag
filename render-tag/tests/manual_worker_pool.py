import sys
import time
import logging
from pathlib import Path
from render_tag.orchestration.worker_pool import WorkerPool
from render_tag.schema.hot_loop import CommandType

logging.basicConfig(level=logging.INFO)

def run_demo():
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    
    # Create a dummy backend script
    dummy_script = Path("dummy_demo_backend.py")
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

    print("
--- Starting Worker Pool Demo ---")
    with WorkerPool(
        num_workers=2,
        base_port=6000,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False
    ) as pool:
        print("Pool started. Checking all workers...")
        responses = pool.execute_on_all(CommandType.STATUS)
        for i, resp in enumerate(responses):
            print(f"Worker {i} STATUS: {resp.status}")

        print("
--- Testing Resilience ---")
        worker = pool.get_worker()
        print(f"Acquired {worker.worker_id}. Killing it...")
        worker.process.kill()
        time.sleep(1)
        
        print("Releasing killed worker back to pool...")
        pool.release_worker(worker)
        
        print("Acquiring worker again (should be restarted)...")
        reborn = pool.get_worker()
        print(f"Acquired {reborn.worker_id}. Is healthy: {reborn.is_healthy()}")
        pool.release_worker(reborn)

    dummy_script.unlink()
    print("--- Demo Complete ---")

if __name__ == "__main__":
    run_demo()
