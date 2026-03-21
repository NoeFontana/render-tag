import time
from unittest.mock import MagicMock

from render_tag.core.schema.hot_loop import Telemetry, WorkerSnapshot, WorkerStatus
from render_tag.orchestration.monitor import HealthMonitor
from render_tag.orchestration.orchestrator import OrchestratorConfig, UnifiedWorkerOrchestrator


def test_check_worker_health_latency():
    """Benchmark _check_worker_health to ensure it is < 1ms."""
    config = OrchestratorConfig(mock=True)
    orchestrator = UnifiedWorkerOrchestrator(config=config)
    monitor = HealthMonitor()
    orchestrator.monitor = monitor

    try:
        worker = MagicMock()
        worker.worker_id = "worker-0"
        worker.client = MagicMock()

        # Pre-populate monitor
        telemetry = Telemetry(
            status=WorkerStatus.IDLE,
            vram_used_mb=0,
            vram_total_mb=0,
            ram_used_mb=0,
            cpu_usage_percent=0,
            state_hash="h",
            uptime_seconds=0,
        )
        monitor._registry["worker-0"] = WorkerSnapshot(
            worker_id="worker-0", telemetry=telemetry, last_seen=time.time(), liveness="HEALTHY"
        )

        # Warmup
        orchestrator._check_worker_health(worker, False)

        # Benchmark 1000 calls
        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            orchestrator._check_worker_health(worker, False)
        duration = time.perf_counter() - start

        avg_latency_ms = (duration / iterations) * 1000
        print(f"Average _check_worker_health latency: {avg_latency_ms:.4f}ms")

        assert avg_latency_ms < 1.0, f"Latency too high: {avg_latency_ms:.4f}ms"
    finally:
        monitor.stop()


def test_worker_restart_on_resource_limit():
    """Verify that orchestrator restarts worker when monitor reports limit exceeded."""
    config = OrchestratorConfig(mock=True)
    orchestrator = UnifiedWorkerOrchestrator(config=config)
    monitor = HealthMonitor()
    orchestrator.monitor = monitor

    try:
        worker = MagicMock()
        worker.worker_id = "worker-0"
        worker.client = MagicMock()
        worker.is_healthy.return_value = True

        # Report RESOURCE_LIMIT_EXCEEDED via monitor
        telemetry = Telemetry(
            status=WorkerStatus.RESOURCE_LIMIT_EXCEEDED,
            vram_used_mb=0,
            vram_total_mb=0,
            ram_used_mb=0,
            cpu_usage_percent=0,
            state_hash="h",
            uptime_seconds=0,
        )
        monitor._registry["worker-0"] = WorkerSnapshot(
            worker_id="worker-0", telemetry=telemetry, last_seen=time.time(), liveness="HEALTHY"
        )

        should_restart, limit_exceeded = orchestrator._check_worker_health(worker, False)

        assert should_restart is True
        assert limit_exceeded is True
    finally:
        monitor.stop()
