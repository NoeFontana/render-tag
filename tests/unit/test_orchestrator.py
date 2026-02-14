import pytest

from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator
from render_tag.core.schema.hot_loop import ResponseStatus


@pytest.mark.timeout(30)
def test_unified_orchestrator_ephemeral(tmp_path):
    output_dir = tmp_path / "unified_output"
    print("\n[TEST] Starting ephemeral test...")

    # Use 1 worker in ephemeral mode (max_renders=1)
    with UnifiedWorkerOrchestrator(
        num_workers=1,
        base_port=5620,
        use_blenderproc=False,
        mock=True,
        ephemeral=True,
        max_renders_per_worker=1,
    ) as orchestrator:
        print("[TEST] Orchestrator started.")
        recipe = {
            "scene_id": 100,
            "world": {},
            "objects": [],
            "cameras": [
                {
                    "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
                    "intrinsics": {"resolution": [100, 100]},
                }
            ],
        }

        print("[TEST] Executing recipe...")
        resp = orchestrator.execute_recipe(recipe, output_dir)
        print(f"[TEST] Execution finished: {resp.status}")
        assert resp.status == ResponseStatus.SUCCESS

        # Verify telemetry was collected
        df = orchestrator.auditor.get_dataframe()
        assert not df.is_empty()
        assert "worker-0" in df["worker_id"].to_list()
    print("[TEST] Ephemeral test complete.")


@pytest.mark.timeout(30)
def test_unified_orchestrator_persistent(tmp_path):
    output_dir = tmp_path / "unified_persistent"
    print("\n[TEST] Starting persistent test...")

    with UnifiedWorkerOrchestrator(
        num_workers=1, base_port=5630, use_blenderproc=False, mock=True, ephemeral=False
    ) as orchestrator:
        print("[TEST] Orchestrator started.")
        for i in range(3):
            recipe = {
                "scene_id": i,
                "world": {},
                "objects": [],
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
            print(f"[TEST] Executing recipe {i}...")
            resp = orchestrator.execute_recipe(recipe, output_dir)
            assert resp.status == ResponseStatus.SUCCESS

        df = orchestrator.auditor.get_dataframe()
        assert len(df) >= 3
    print("[TEST] Persistent test complete.")
