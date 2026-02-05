"""
Benchmark script comparing Cold startup vs Hot Loop throughput.
"""

import sys
import time
import json
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from render_tag.orchestration.executors import LocalExecutor
from render_tag.orchestration.worker_pool import WorkerPool
from render_tag.schema.hot_loop import CommandType

logging.basicConfig(level=logging.ERROR)

def run_benchmark():
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    backend_script = src_path / "render_tag" / "backend" / "zmq_server.py"
    output_dir = project_root / "output" / "benchmark_hot_loop"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    recipe = {
        "scene_id": 0,
        "world": {},
        "objects": [{"type": "TAG", "location": [0,0,0], "rotation_euler": [0,0,0], 
                     "properties": {"tag_family": "test", "tag_id": 0, "tag_size": 0.1}}],
        "cameras": [{"transform_matrix": [[1,0,0,0],[0,1,0,0],[0,0,1,2],[0,0,0,1]], 
                     "intrinsics": {"resolution": [100, 100]}}]
    }

    count = 5
    print(f"--- Benchmarking {count} renders ---")

    # 1. Cold Baseline (Simulated)
    print("\n[COLD] Starting Cold Baseline...")
    cold_time = (3.0 * count) + 0.5 
    print(f"COLD (Simulated): {cold_time:.2f}s total ({60/(cold_time/count):.2f} img/min)")

    # 2. Hot Loop
    print("\n[HOT] Starting Hot Loop...")
    with WorkerPool(
        num_workers=1,
        base_port=7200,
        blender_script=backend_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        mock=True
    ) as pool:
        worker = pool.get_worker()
        loop_start = time.time()
        for i in range(count):
            worker.send_command(CommandType.RENDER, payload={
                "recipe": recipe, 
                "output_dir": str(output_dir), 
                "skip_visibility": True
            })
        loop_end = time.time()
        pool.release_worker(worker)
    
    hot_time = loop_end - loop_start
    print(f"HOT (Measured): {hot_time:.2f}s total ({60/(hot_time/count):.2f} img/min)")
    
    improvement = cold_time / hot_time
    print(f"\nSpeedup (Mock): {improvement:.1f}x")

if __name__ == "__main__":
    run_benchmark()