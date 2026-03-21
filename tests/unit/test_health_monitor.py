import json

from render_tag.core.schema.hot_loop import Telemetry, WorkerStatus
from render_tag.orchestration.monitor import HealthMonitor


def test_health_monitor_ingestion():
    """Verify HealthMonitor correctly updates its registry from ZMQ messages."""
    monitor = HealthMonitor()

    worker_id = "worker-0"
    telemetry = Telemetry(
        status=WorkerStatus.IDLE,
        vram_used_mb=512.0,
        vram_total_mb=8192.0,
        ram_used_mb=1024.0,
        cpu_usage_percent=15.0,
        state_hash="test-hash",
        uptime_seconds=10.0,
        object_count=10,
        active_scene_id=None,
    )

    # Manually ingest a message
    payload = telemetry.model_dump_json().encode("utf-8")
    monitor._process_message(worker_id.encode("utf-8"), payload)

    snapshot = monitor.get_snapshot(worker_id)
    assert snapshot is not None
    assert snapshot.worker_id == worker_id
    assert snapshot.telemetry.cpu_usage_percent == 15.0
    assert snapshot.liveness == "HEALTHY"


def test_health_monitor_missing_worker():
    """Verify HealthMonitor returns None for unknown workers."""
    monitor = HealthMonitor()
    assert monitor.get_snapshot("unknown") is None


def test_health_monitor_persistence(tmp_path):
    """Verify HealthMonitor persists telemetry to NDJSON."""
    log_file = tmp_path / "telemetry.ndjson"
    monitor = HealthMonitor(log_path=log_file)

    telemetry = Telemetry(
        status=WorkerStatus.IDLE,
        vram_used_mb=1.0,
        vram_total_mb=2.0,
        ram_used_mb=3.0,
        cpu_usage_percent=4.0,
        state_hash="h",
        uptime_seconds=5.0,
    )
    monitor._process_message(b"w1", telemetry.model_dump_json().encode())

    assert log_file.exists()
    with open(log_file) as f:
        line = f.readline()
        data = json.loads(line)
        assert data["worker_id"] == "w1"
        assert data["telemetry"]["cpu_usage_percent"] == 4.0
        assert "timestamp" in data
