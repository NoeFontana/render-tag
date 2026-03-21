
import pytest
from unittest.mock import MagicMock, patch
from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator, OrchestratorConfig
from render_tag.orchestration.monitor import HealthMonitor
from render_tag.core.schema.hot_loop import Telemetry, WorkerStatus, WorkerSnapshot, Response, ResponseStatus

def test_orchestrator_uses_monitor():
    """Verify that _check_worker_health uses HealthMonitor instead of sending STATUS command."""
    config = OrchestratorConfig(mock=True)
    orchestrator = UnifiedWorkerOrchestrator(config=config)
    monitor = MagicMock(spec=HealthMonitor)
    orchestrator.monitor = monitor
    
    worker = MagicMock()
    worker.worker_id = "worker-0"
    worker.client = MagicMock()
    
    # Setup mock snapshot in monitor
    telemetry = Telemetry(
        status=WorkerStatus.IDLE,
        vram_used_mb=0,
        vram_total_mb=0,
        ram_used_mb=0,
        cpu_usage_percent=0,
        state_hash="h",
        uptime_seconds=0
    )
    monitor.get_snapshot.return_value = WorkerSnapshot(
        worker_id="worker-0",
        telemetry=telemetry,
        last_seen=100.0,
        liveness="HEALTHY"
    )
    
    # Call _check_worker_health
    should_restart, limit_exceeded = orchestrator._check_worker_health(worker, False)
    
    # Verify monitor was called
    monitor.get_snapshot.assert_called_with("worker-0")
    
    # Verify NO STATUS command was sent
    # (Checking if worker.send_command was NOT called with CommandType.STATUS)
    from render_tag.core.schema.hot_loop import CommandType
    for call in worker.send_command.call_args_list:
        assert call[0][0] != CommandType.STATUS
