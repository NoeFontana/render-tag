import sys
import time
import logging
from pathlib import Path
from render_tag.orchestration.worker_pool import WorkerPool
from render_tag.schema.hot_loop import CommandType

logging.basicConfig(level=logging.INFO)

def run_perf_demo():
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    backend_script = src_path / "render_tag" / "backend" / "zmq_server.py"
    output_dir = Path("hot_loop_perf_test")
    
    print("
--- Starting Hot Loop Performance Demo ---")
    with WorkerPool(
        num_workers=1,
        base_port=7000,
        blender_script=backend_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        mock=True
    ) as pool:
        worker = pool.get_worker()
        
        # 1. Warm up
        print("Warming up backend...")
        worker.send_command(CommandType.INIT, payload={"parameters": {"session": "perf-test"}})
        
        # 2. Benchmark Loop
        count = 20
        start = time.time()
        for i in range(count):
            recipe = {
                "scene_id": i,
                "world": {},
                "objects": [{"type": "TAG", "location": [0,0,0], "rotation_euler": [0,0,0], 
                             "properties": {"tag_family": "test", "tag_id": i, "tag_size": 0.1}}],
                "cameras": [{"transform_matrix": [[1,0,0,0],[0,1,0,0],[0,0,1,2],[0,0,0,1]], 
                             "intrinsics": {"resolution": [100, 100]}}]
            }
            worker.send_command(
                CommandType.RENDER,
                payload={"recipe": recipe, "output_dir": str(output_dir), "skip_visibility": True}
            )
            if i % 5 == 0: print(f"Rendered {i}/{count}...")
            
        end = time.time()
        total = end - start
        print(f"
Benchmark Complete!")
        print(f"Total time for {count} scenes: {total:.4f}s")
        print(f"Average time per scene: {total/count:.4f}s")
        print(f"Projected throughput: {60 / (total/count):.2f} images/min")

    print("--- Demo Complete ---")

if __name__ == "__main__":
    run_perf_demo()
