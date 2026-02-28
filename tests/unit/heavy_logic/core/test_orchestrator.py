from unittest.mock import MagicMock, patch

from render_tag.core.schema.hot_loop import Response, ResponseStatus
from render_tag.orchestration import UnifiedWorkerOrchestrator


@patch("render_tag.orchestration.orchestrator.PersistentWorkerProcess")
def test_unified_orchestrator_ephemeral(mock_worker_cls, tmp_path):
    output_dir = tmp_path / "unified_output"

    # Configure mock
    mock_worker = MagicMock()
    mock_worker.worker_id = "worker-0"
    mock_worker.is_healthy.return_value = True
    mock_worker.max_renders = None
    mock_worker.renders_completed = 0
    # Simulate a successful render response
    mock_worker.send_command.return_value = Response(
        status=ResponseStatus.SUCCESS,
        request_id="test-ephemeral",
        message="Mock success",
        data={
            "vram_used_mb": 100,
            "vram_total_mb": 8000,
            "cpu_usage_percent": 10,
            "state_hash": "abc",
            "uptime_seconds": 10,
            "status": "IDLE",
        },
    )
    mock_worker_cls.return_value = mock_worker

    with UnifiedWorkerOrchestrator(
        num_workers=1,
        mock=True,
        ephemeral=True,
        max_renders_per_worker=1,
    ) as orchestrator:
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

        resp = orchestrator.execute_recipe(recipe, output_dir)
        assert resp.status == ResponseStatus.SUCCESS

        # Verify telemetry was collected
        df = orchestrator.auditor.get_dataframe()
        assert not df.is_empty()
        assert "worker-0" in df["worker_id"].to_list()


@patch("render_tag.orchestration.orchestrator.PersistentWorkerProcess")
def test_unified_orchestrator_persistent(mock_worker_cls, tmp_path):
    output_dir = tmp_path / "unified_persistent"

    mock_worker = MagicMock()
    mock_worker.worker_id = "worker-0"
    mock_worker.is_healthy.return_value = True
    mock_worker.max_renders = None
    mock_worker.renders_completed = 0
    mock_worker.send_command.return_value = Response(
        status=ResponseStatus.SUCCESS,
        request_id="test-persistent",
        message="Mock success",
        data={
            "vram_used_mb": 100,
            "vram_total_mb": 8000,
            "cpu_usage_percent": 10,
            "state_hash": "abc",
            "uptime_seconds": 10,
            "status": "IDLE",
        },
    )
    mock_worker_cls.return_value = mock_worker

    with UnifiedWorkerOrchestrator(num_workers=1, mock=True, ephemeral=False) as orchestrator:
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
            resp = orchestrator.execute_recipe(recipe, output_dir)
            assert resp.status == ResponseStatus.SUCCESS

        df = orchestrator.auditor.get_dataframe()
        assert len(df) >= 3
