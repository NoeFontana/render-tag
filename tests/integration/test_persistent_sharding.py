import sys
from pathlib import Path

from render_tag.orchestration.orchestrator_utils import UnifiedWorkerOrchestrator


def test_hot_loop_end_to_end(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    src_path = project_root / "src"

    # We use our real backend script but with python (mocked bproc/bpy)
    backend_script = src_path / "render_tag" / "backend" / "zmq_server.py"

    output_dir = tmp_path / "output"

    with UnifiedWorkerOrchestrator(
        num_workers=1,
        base_port=5600,
        blender_script=backend_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        mock=True,
    ) as pool:
        # 1. Create a dummy recipe
        recipe = {
            "scene_id": 0,
            "world": {},
            "objects": [],
            "cameras": [
                {
                    "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
                    "intrinsics": {"resolution": [100, 100]},
                }
            ],
        }

        # 2. Execute via orchestrator
        resp = pool.execute_recipe(recipe, output_dir)
        assert resp.status.value == "SUCCESS"

        # 3. Verify output
        assert (output_dir / "images" / "scene_0000_cam_0000.png").exists()
