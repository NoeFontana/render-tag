from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from render_tag.core.errors import WorkerCommunicationError
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


def test_stopped_worker_not_released_without_restart():
    """Verify that a worker stopped due to error goes through release_worker (which restarts it)
    rather than being put back into the pool in a dead state."""
    orch = UnifiedWorkerOrchestrator(num_workers=1, mock=True)
    orch.running = True

    mock_worker = MagicMock()
    mock_worker.worker_id = "test-worker"
    mock_worker.shard_id = "0_abc"
    mock_worker.memory_limit_mb = 1024
    mock_worker.max_renders = None
    mock_worker.renders_completed = 0
    mock_worker.client = None  # Skip telemetry check in release_worker
    mock_worker.process = None  # Mark as dead — forces restart in _check_worker_health
    mock_worker.is_healthy.return_value = False

    # Worker raises on send_command (simulating a crash)
    mock_worker.send_command.side_effect = ConnectionError("worker crashed")

    orch.worker_queue.put(mock_worker)

    # Create a replacement worker that the restart path will return
    replacement = MagicMock()
    replacement.worker_id = "test-worker"
    replacement.is_healthy.return_value = True
    replacement.max_renders = None
    replacement.renders_completed = 0
    replacement.client = MagicMock()
    replacement.process = MagicMock()

    resp_ok = Response(status=ResponseStatus.SUCCESS, request_id="req2", message="OK")
    replacement.send_command.return_value = resp_ok

    with patch(
        "render_tag.orchestration.orchestrator.PersistentWorkerProcess", return_value=replacement
    ):
        # Put the replacement in the queue for the retry iteration
        # (release_worker will restart mock_worker -> replacement, then put it back)
        recipe = {"scene_id": 1}
        resp = orch.execute_recipe(recipe, Path("output"))

    assert resp.status == ResponseStatus.SUCCESS
    # The original worker must have been stopped
    mock_worker.stop.assert_called()
    # The replacement worker served the successful render
    replacement.send_command.assert_called()


def test_execute_recipe_release_on_success():
    """Verify worker is released back to pool after successful render."""
    orch = UnifiedWorkerOrchestrator(num_workers=1, mock=True)
    orch.running = True

    mock_worker = MagicMock()
    mock_worker.worker_id = "test-worker"
    mock_worker.shard_id = "0_abc"
    mock_worker.renders_completed = 0
    mock_worker.max_renders = None
    mock_worker.client = MagicMock()
    mock_worker.process = MagicMock()
    mock_worker.is_healthy.return_value = True

    resp_ok = Response(status=ResponseStatus.SUCCESS, request_id="req1", message="OK")
    mock_worker.send_command.return_value = resp_ok

    orch.worker_queue.put(mock_worker)

    with patch.object(orch, "release_worker") as mock_release:
        resp = orch.execute_recipe({"scene_id": 1}, Path("output"))

    assert resp.status == ResponseStatus.SUCCESS
    # release_worker must be called exactly once
    mock_release.assert_called_once_with(mock_worker)


def test_execute_recipe_release_on_failure():
    """Verify worker is released (not leaked) after all retries are exhausted."""
    orch = UnifiedWorkerOrchestrator(num_workers=1, mock=True)
    orch.running = True

    mock_worker = MagicMock()
    mock_worker.worker_id = "test-worker"
    mock_worker.shard_id = "0_abc"
    mock_worker.renders_completed = 0
    mock_worker.max_renders = None
    mock_worker.client = None
    mock_worker.process = None
    mock_worker.is_healthy.return_value = False

    mock_worker.send_command.side_effect = ConnectionError("dead")

    # Put worker 3 times (initial + 2 retries)
    for _ in range(3):
        orch.worker_queue.put(mock_worker)

    with (
        patch.object(orch, "release_worker") as mock_release,
        pytest.raises(WorkerCommunicationError),
    ):
        orch.execute_recipe({"scene_id": 1}, Path("output"))

    # release_worker must be called for every attempt (3 times)
    assert mock_release.call_count == 3
