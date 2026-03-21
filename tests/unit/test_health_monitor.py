
import json
import time
from unittest.mock import MagicMock, patch

import pytest
import zmq

from render_tag.orchestration.monitor import HealthMonitor
from render_tag.core.schema.hot_loop import Telemetry, WorkerStatus, WorkerSnapshot

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
        active_scene_id=None
    )
    
    # Manually ingest a message
    payload = telemetry.model_dump_json().encode('utf-8')
    monitor._process_message(worker_id.encode('utf-8'), payload)
    
    snapshot = monitor.get_snapshot(worker_id)
    assert snapshot is not None
    assert snapshot.worker_id == worker_id
    assert snapshot.telemetry.cpu_usage_percent == 15.0
    assert snapshot.liveness == "HEALTHY"

def test_health_monitor_missing_worker():
    """Verify HealthMonitor returns None for unknown workers."""
    monitor = HealthMonitor()
    assert monitor.get_snapshot("unknown") is None

def test_health_monitor_stress_ingestion():
    """Verify HealthMonitor handles high frequency updates for multiple workers."""
    monitor = HealthMonitor()
    
    worker_ids = [f"w-{i}" for i in range(10)]
    telemetry_base = {
        "status": WorkerStatus.BUSY,
        "vram_used_mb": 0.0,
        "vram_total_mb": 0.0,
        "ram_used_mb": 0.0,
        "cpu_usage_percent": 0.0,
        "state_hash": "h",
        "uptime_seconds": 0.0
    }
    
    # Simulate 1000 messages
    for i in range(1000):
        w_id = worker_ids[i % 10]
        telemetry_data = telemetry_base.copy()
        telemetry_data["cpu_usage_percent"] = float(i)
        payload = Telemetry(**telemetry_data).model_dump_json().encode()
        monitor._process_message(w_id.encode(), payload)
        
    snapshots = monitor.get_all_snapshots()
    assert len(snapshots) == 10
    for w_id in worker_ids:
        # Latest message for w-9 was i=999
        # Latest message for w-0 was i=990
        # etc.
        assert snapshots[w_id].telemetry.cpu_usage_percent >= 990.0
