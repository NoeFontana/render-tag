import threading
import time
import pytest
from render_tag.core.schema.hot_loop import CommandType, ResponseStatus
from render_tag.orchestration.orchestrator import ZmqHostClient
from render_tag.backend.zmq_server import ZmqBackendServer


def test_host_backend_loopback():
    port = 5558
    server = ZmqBackendServer(port=port)

    # Start server in background thread
    server_thread = threading.Thread(target=server.run)
    server_thread.daemon = True  # Ensure it dies if test crashes
    server_thread.start()

    time.sleep(0.1)  # Wait for bind

    try:
        with ZmqHostClient(port=port) as client:
            # 1. Test STATUS
            resp = client.send_command(CommandType.STATUS)
            assert resp.status == ResponseStatus.SUCCESS
            assert "state_hash" in resp.data
            assert len(resp.data["state_hash"]) > 0

            # 2. Test INIT
            resp = client.send_command(CommandType.INIT, payload={"assets": ["test.exr"]})
            assert resp.status == ResponseStatus.SUCCESS
            assert "1 assets resident" in resp.message

            # 3. Test RESET
            resp = client.send_command(CommandType.RESET)
            assert resp.status == ResponseStatus.SUCCESS
            assert "Reset" in resp.message

    finally:
        server.stop()
