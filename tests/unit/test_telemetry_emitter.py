
import json
import time
from unittest.mock import MagicMock, patch

import pytest
import zmq

from render_tag.backend.telemetry import TelemetryEmitter
from render_tag.core.schema.hot_loop import Telemetry, WorkerStatus

@patch("zmq.Context")
def test_telemetry_emitter_basic(mock_context):
    """Verify TelemetryEmitter initializes and emits data."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket
    
    worker_id = "test-worker"
    emitter = TelemetryEmitter(worker_id=worker_id, port=9999, interval_ms=1)
    
    emitter.running = True
    def stop_loop(*args, **kwargs):
        emitter.running = False
        return None
    mock_socket.send_multipart.side_effect = stop_loop

    with patch.object(emitter, "poll_metrics") as mock_poll:
        mock_poll.return_value = Telemetry(
            status=WorkerStatus.IDLE,
            vram_used_mb=100.0,
            vram_total_mb=1000.0,
            cpu_usage_percent=10.0,
            state_hash="abc",
            uptime_seconds=5.0
        )
        emitter._loop()
        
    assert mock_socket.send_multipart.called
    
def test_telemetry_emitter_payload(tmp_path):
    """Verify the payload sent by emitter matches schema."""
    with patch("zmq.Context") as mock_context:
        mock_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_socket
        
        emitter = TelemetryEmitter(worker_id="w1", port=9999, interval_ms=10)
        
        # Test poll_metrics directly
        t = emitter.poll_metrics()
        assert isinstance(t, Telemetry)
        assert t.state_hash == "standalone"
        
        # Test emission logic (one-shot)
        emitter.running = True
        
        def side_effect(*args, **kwargs):
            emitter.running = False # Stop after first send
            return None
            
        mock_socket.send_multipart.side_effect = side_effect
        
        emitter._loop()
        
        mock_socket.send_multipart.assert_called_once()
        topic, payload = mock_socket.send_multipart.call_args[0][0]
        assert topic == b"w1"
        data = json.loads(payload.decode('utf-8'))
        assert data["status"] == "IDLE"
        assert "ram_used_mb" in data
