
import json
import time
from pathlib import Path
import pytest
from render_tag.orchestration.monitor import HealthMonitor
from render_tag.core.schema.hot_loop import Telemetry, WorkerStatus

def test_telemetry_burst_and_persistence(tmp_path):
    """Verify HealthMonitor handles rapid bursts and maintains log integrity."""
    log_file = tmp_path / "telemetry_burst.ndjson"
    monitor = HealthMonitor(log_path=log_file)
    
    worker_id = "burst-worker"
    num_messages = 100
    
    for i in range(num_messages):
        telemetry = Telemetry(
            status=WorkerStatus.BUSY,
            vram_used_mb=float(i), vram_total_mb=1000.0, ram_used_mb=0.0,
            cpu_usage_percent=0.0, state_hash="h", uptime_seconds=float(i)
        )
        monitor._process_message(worker_id.encode(), telemetry.model_dump_json().encode())
        
    # Verify registry has the LAST message
    snap = monitor.get_snapshot(worker_id)
    assert snap.telemetry.vram_used_mb == 99.0
    
    # Verify NDJSON has ALL messages
    assert log_file.exists()
    with open(log_file) as f:
        lines = f.readlines()
        assert len(lines) == num_messages
        
        # Verify order and integrity of some messages
        first = json.loads(lines[0])
        assert first["telemetry"]["vram_used_mb"] == 0.0
        
        last = json.loads(lines[-1])
        assert last["telemetry"]["vram_used_mb"] == 99.0

def test_watchdog_multi_worker_staggered(tmp_path):
    """Verify Watchdog handles multiple workers with different liveness states."""
    monitor = HealthMonitor()
    
    # worker-1: last seen at t=90 (will be UNRESPONSIVE at t=105)
    # worker-2: last seen at t=98 (will be HEALTHY at t=105)
    
    tel = Telemetry(
        status=WorkerStatus.IDLE,
        vram_used_mb=0, vram_total_mb=0, ram_used_mb=0,
        cpu_usage_percent=0, state_hash="h", uptime_seconds=0
    )
    
    from unittest.mock import patch
    
    with patch("time.time", return_value=90.0):
        monitor._process_message(b"worker-1", tel.model_dump_json().encode())
    
    with patch("time.time", return_value=98.0):
        monitor._process_message(b"worker-2", tel.model_dump_json().encode())
        
    # Sweep at t=105
    with patch("time.time", return_value=105.0):
        monitor._check_liveness()
        
    assert monitor.get_snapshot("worker-1").liveness == "UNRESPONSIVE"
    assert monitor.get_snapshot("worker-2").liveness == "HEALTHY"
