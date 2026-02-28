from unittest.mock import MagicMock, patch

from render_tag.backend.worker_server import ZmqBackendServer
from render_tag.core.schema.hot_loop import WorkerStatus


def test_worker_memory_enforcement():
    """Verify that worker shuts down when memory limit is exceeded."""
    server = ZmqBackendServer(port=5580, memory_limit_mb=100)

    mock_process = MagicMock()
    # Return 150MB (exceeds 100MB limit)
    mock_process.memory_info.return_value.rss = 150 * 1024 * 1024

    with (
        patch("psutil.Process", return_value=mock_process),
        patch("zmq.Context"),
        patch("render_tag.backend.bridge.bridge.stabilize"),
    ):
        server.running = True
        # Run check
        server._check_memory()

        assert server.status == WorkerStatus.RESOURCE_LIMIT_EXCEEDED
        assert not server.running


def test_worker_memory_within_limit():
    """Verify that worker continues running when within memory limits."""
    server = ZmqBackendServer(port=5581, memory_limit_mb=500)

    mock_process = MagicMock()
    # Return 150MB (within 500MB limit)
    mock_process.memory_info.return_value.rss = 150 * 1024 * 1024

    with (
        patch("psutil.Process", return_value=mock_process),
        patch("zmq.Context"),
        patch("render_tag.backend.bridge.bridge.stabilize"),
    ):
        server.running = True
        server._check_memory()

        assert server.status == WorkerStatus.IDLE
        assert server.running
