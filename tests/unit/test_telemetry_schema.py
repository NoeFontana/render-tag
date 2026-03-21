
import pytest
from pydantic import ValidationError
from render_tag.core.schema.hot_loop import Telemetry, WorkerStatus

def test_telemetry_new_fields():
    """Verify Telemetry schema supports object_count and active_scene_id."""
    data = {
        "status": WorkerStatus.BUSY,
        "vram_used_mb": 1024.0,
        "vram_total_mb": 8192.0,
        "ram_used_mb": 512.0,
        "cpu_usage_percent": 25.5,
        "state_hash": "hash123",
        "uptime_seconds": 100.0,
        "object_count": 42,
        "active_scene_id": 5
    }
    t = Telemetry(**data)
    assert t.object_count == 42
    assert t.active_scene_id == 5

def test_telemetry_defaults():
    """Verify Telemetry defaults for new fields."""
    data = {
        "status": WorkerStatus.IDLE,
        "vram_used_mb": 0.0,
        "vram_total_mb": 8192.0,
        "cpu_usage_percent": 0.0,
        "state_hash": "empty",
        "uptime_seconds": 0.0
    }
    t = Telemetry(**data)
    assert t.object_count == 0
    assert t.active_scene_id is None
