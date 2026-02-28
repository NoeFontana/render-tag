from unittest.mock import MagicMock, patch

from render_tag.core.schema.hot_loop import Response, ResponseStatus
from render_tag.orchestration import UnifiedWorkerOrchestrator


@patch("render_tag.orchestration.orchestrator.PersistentWorkerProcess")
def test_vram_guardrail_restart(mock_worker_cls, tmp_path):
    """Verify that a worker is restarted if it exceeds VRAM threshold."""

    # Setup mock for first worker (high VRAM)
    m1 = MagicMock()
    m1.worker_id = "worker-0"
    m1.is_healthy.return_value = True
    m1.max_renders = None
    m1.renders_completed = 0
    m1.client = MagicMock()
    # High VRAM telemetry (2000MB > 1000MB threshold)
    m1.send_command.return_value = Response(
        status=ResponseStatus.SUCCESS,
        request_id="test-req",
        message="VRAM heavy",
        data={
            "vram_used_mb": 2000,
            "vram_total_mb": 8000,
            "cpu_usage_percent": 50,
            "status": "IDLE",
            "state_hash": "mock_hash",
            "uptime_seconds": 123.4,
        },
    )

    # Setup mock for second worker (restarted one)
    m2 = MagicMock()
    m2.worker_id = "worker-0"
    m2.is_healthy.return_value = True

    mock_worker_cls.side_effect = [m1, m2]

    # Start pool with low threshold (1000 MB)
    with UnifiedWorkerOrchestrator(
        num_workers=1,
        mock=True,
        vram_threshold_mb=1000,
    ) as pool:
        worker = pool.get_worker()
        assert worker is m1

        # Releasing should trigger VRAM check -> STATUS command -> High VRAM -> Restart
        pool.release_worker(worker)

        # Should have called constructor again for restart
        assert mock_worker_cls.call_count == 2

        worker_new = pool.get_worker()
        assert worker_new is m2
