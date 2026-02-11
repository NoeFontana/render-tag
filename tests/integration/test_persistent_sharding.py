import sys
import time
from pathlib import Path

from render_tag.orchestration.worker_pool import WorkerPool
from render_tag.schema.hot_loop import CommandType, ResponseStatus


def test_hot_loop_end_to_end(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    src_path = project_root / "src"

    # We use our real backend script but with python (mocked bproc/bpy)
    backend_script = src_path / "render_tag" / "backend" / "zmq_server.py"

    output_dir = tmp_path / "output"

    with WorkerPool(
        num_workers=1,
        base_port=5600,
        blender_script=backend_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        mock=True,
    ) as pool:
        worker = pool.get_worker()

        start_time = time.time()

        for i in range(10):
            recipe = {
                "scene_id": i,
                "world": {},
                "objects": [
                    {
                        "type": "TAG",
                        "location": [0, 0, 0],
                        "rotation_euler": [0, 0, 0],
                        "properties": {"tag_family": "test", "tag_id": i, "tag_size": 0.1},
                    }
                ],
                "cameras": [
                    {
                        "transform_matrix": [
                            [1, 0, 0, 0],
                            [0, 1, 0, 0],
                            [0, 0, 1, 2],
                            [0, 0, 0, 1],
                        ],
                        "intrinsics": {"resolution": [100, 100]},
                    }
                ],
            }

            resp = worker.send_command(
                CommandType.RENDER,
                payload={"recipe": recipe, "output_dir": str(output_dir), "skip_visibility": True},
            )
            if resp.status != ResponseStatus.SUCCESS:
                print(f"DEBUG: Render {i} failed: {resp.message}")
            assert resp.status == ResponseStatus.SUCCESS

        total_time = time.time() - start_time
        avg_time = total_time / 10

        print(f"\nTotal time for 10 renders: {total_time:.2f}s (Avg: {avg_time:.2f}s)")

        assert avg_time < 1.0

        pool.release_worker(worker)
