import threading
import time

from render_tag.backend.zmq_server import ZmqBackendServer
from render_tag.orchestration.zmq_client import ZmqHostClient
from render_tag.schema.hot_loop import CommandType, ResponseStatus


def test_ephemeral_mode(tmp_path):
    port = 5610
    server = ZmqBackendServer(port=port)

    # Start server in background thread with max_renders=1
    server_thread = threading.Thread(target=server.run, kwargs={"max_renders": 1})
    server_thread.daemon = True
    server_thread.start()

    time.sleep(0.1)

    output_dir = tmp_path / "ephemeral_output"
    recipe = {
        "scene_id": 1,
        "world": {},
        "objects": [],
        "cameras": [
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
                "intrinsics": {"resolution": [100, 100]},
            }
        ],
    }

    try:
        with ZmqHostClient(port=port) as client:
            resp = client.send_command(
                CommandType.RENDER,
                payload={"recipe": recipe, "output_dir": str(output_dir), "skip_visibility": True},
            )
            assert resp.status == ResponseStatus.SUCCESS

        # Server should shutdown automatically after 1 render
        server_thread.join(timeout=2.0)
        assert not server_thread.is_alive()

    finally:
        server.stop()
