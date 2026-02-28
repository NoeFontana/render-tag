from pathlib import Path
from unittest.mock import MagicMock, patch

from render_tag.core.schema.hot_loop import Response, ResponseStatus
from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator


def test_orchestrator_maintenance_restart():
    """Verify that orchestrator retries on RESOURCE_LIMIT_EXCEEDED without counting as failure."""
    orch = UnifiedWorkerOrchestrator(num_workers=1, mock=True)
    orch.running = True

    mock_worker = MagicMock()
    mock_worker.worker_id = "test-worker"
    mock_worker.shard_id = "0_abc"
    mock_worker.memory_limit_mb = 1024

    # First call returns RESOURCE_LIMIT_EXCEEDED
    resp_limit = Response(
        status=ResponseStatus.FAILURE, request_id="req1", message="RESOURCE_LIMIT_EXCEEDED: test"
    )
    # Second call returns SUCCESS
    resp_ok = Response(status=ResponseStatus.SUCCESS, request_id="req2", message="OK")

    mock_worker.send_command.side_effect = [resp_limit, resp_ok]

    # We need to ensure get_worker() returns our mock twice
    # execute_recipe calls get_worker at the start of every loop iteration
    # release_worker (mocked) should put it back if we weren't mocking it,
    # but since we mock it, we just need to pre-fill the queue.
    orch.worker_queue.put(mock_worker)
    orch.worker_queue.put(mock_worker)  # Put it twice for the retry

    with patch.object(orch, "release_worker"):
        recipe = {"scene_id": 1}
        resp = orch.execute_recipe(recipe, Path("output"))

        assert resp.status == ResponseStatus.SUCCESS
        assert mock_worker.send_command.call_count == 2
