import pytest
from render_tag.schema.hot_loop import Command, CommandType, Response, ResponseStatus, Telemetry, calculate_state_hash

def test_command_schema():
    cmd = Command(
        command_type=CommandType.INIT,
        payload={"assets": ["hdri1.exr"]},
        request_id="req-123"
    )
    assert cmd.command_type == CommandType.INIT
    assert cmd.request_id == "req-123"
    assert cmd.payload["assets"] == ["hdri1.exr"]

def test_response_schema():
    resp = Response(
        status=ResponseStatus.SUCCESS,
        request_id="req-123",
        message="Initialized",
        data={"vram": 1024}
    )
    assert resp.status == ResponseStatus.SUCCESS
    assert resp.request_id == "req-123"
    assert resp.data["vram"] == 1024

def test_telemetry_schema():
    tel = Telemetry(
        vram_used_mb=512.5,
        vram_total_mb=8192.0,
        cpu_usage_percent=15.0,
        state_hash="abc-123",
        uptime_seconds=100.0
    )
    assert tel.vram_used_mb == 512.5
    assert tel.uptime_seconds == 100.0

def test_state_hash_determinism():
    assets = ["a.exr", "b.png"]
    params = {"exposure": 1.0}
    
    hash1 = calculate_state_hash(assets, params)
    hash2 = calculate_state_hash(reversed(assets), params) # Order should not matter due to sorted()
    
    assert hash1 == hash2
    
    params2 = {"exposure": 1.1}
    hash3 = calculate_state_hash(assets, params2)
    assert hash1 != hash3
