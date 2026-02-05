import threading
import time

from render_tag.backend.zmq_server import ZmqBackendServer
from render_tag.orchestration.zmq_client import ZmqHostClient
from render_tag.schema.hot_loop import CommandType, ResponseStatus


def test_backend_warmup(tmp_path):
    port = 5585
    server = ZmqBackendServer(port=port)
    
    # Start server in background thread
    # Note: We are mocking bproc/bpy being None in this environment
    server_thread = threading.Thread(target=server.run)
    server_thread.daemon = True
    server_thread.start()
    
    time.sleep(0.1)
    
    # Create a dummy asset file
    dummy_hdri = tmp_path / "test.exr"
    dummy_hdri.write_text("dummy hdri data")
    
    try:
        with ZmqHostClient(port=port) as client:
            # Test INIT with assets
            resp = client.send_command(
                CommandType.INIT, 
                payload={
                    "assets": [str(dummy_hdri)],
                    "parameters": {"exposure": 1.5}
                }
            )
            assert resp.status == ResponseStatus.SUCCESS
            assert "state_hash" in resp.data
            initial_hash = resp.data["state_hash"]
            
            # Test STATUS to see telemetry
            resp = client.send_command(CommandType.STATUS)
            assert resp.status == ResponseStatus.SUCCESS
            assert resp.data["state_hash"] == initial_hash
            
            # Test SHUTDOWN
            client.send_command(CommandType.SHUTDOWN)
            
        server_thread.join(timeout=1.0)
        
    finally:
        server.stop()
