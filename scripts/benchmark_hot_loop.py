"""
Benchmark script comparing Cold startup vs Hot Loop throughput using Unified Orchestrator.
"""

import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from render_tag.orchestration.unified_orchestrator import UnifiedWorkerOrchestrator

logging.basicConfig(level=logging.ERROR)


def run_benchmark():
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    src_path / "render_tag" / "backend" / "zmq_server.py"
    output_dir = project_root / "output" / "benchmark_unified"
    output_dir.mkdir(parents=True, exist_ok=True)

    recipe = {
        "scene_id": 0,
        "world": {},
        "objects": [
            {
                "type": "TAG",
                "location": [0, 0, 0],
                "rotation_euler": [0, 0, 0],
                "properties": {"tag_family": "test", "tag_id": 0, "tag_size": 0.1},
            }
        ],
        "cameras": [
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
                "intrinsics": {"resolution": [100, 100]},
            }
        ],
    }

    count = 5
    print(f"--- Benchmarking {count} renders via Unified Orchestrator ---")

    # 1. Cold (Ephemeral) mode
    print("\n[COLD/EPHEMERAL] Starting...")
    start_cold = time.time()
    for _i in range(count):
        # Ephemeral mode: 1 pool per render (simulates legacy behavior but unified)
        with UnifiedWorkerOrchestrator(
            num_workers=1,
            base_port=7300 + _i,
            use_blenderproc=False,
            mock=True,
            ephemeral=True,
            max_renders_per_worker=1,
        ) as orch:
            orch.execute_recipe(recipe, output_dir)
    cold_time = time.time() - start_cold
    print(f"COLD/EPHEMERAL: {cold_time:.2f}s total ({60 / (cold_time / count):.2f} img/min)")

    # 2. Hot Loop (Persistent)
    print("\n[HOT/PERSISTENT] Starting...")
    with UnifiedWorkerOrchestrator(
        num_workers=1, base_port=7400, use_blenderproc=False, mock=True, ephemeral=False
    ) as orch:
        loop_start = time.time()
        for _i in range(count):
            orch.execute_recipe(recipe, output_dir)
        loop_end = time.time()

    hot_time = loop_end - loop_start
    print(f"HOT/PERSISTENT: {hot_time:.2f}s total ({60 / (hot_time / count):.2f} img/min)")

    improvement = cold_time / hot_time
    print(f"\nInternal Hot-Loop Speedup: {improvement:.1f}x")


if __name__ == "__main__":
    run_benchmark()
