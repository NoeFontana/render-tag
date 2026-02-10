import threading
import time

from render_tag.backend.zmq_server import ZmqBackendServer
from render_tag.orchestration.zmq_client import ZmqHostClient
from render_tag.schema.hot_loop import CommandType, ResponseStatus


def test_hot_loop_render_command(tmp_path):
    port = 5590
    server = ZmqBackendServer(port=port)

    server_thread = threading.Thread(target=server.run)
    server_thread.daemon = True
    server_thread.start()

    time.sleep(0.1)

    output_dir = tmp_path / "output"

    # Minimal mock recipe
    recipe = {
        "scene_id": 42,
        "world": {},
        "objects": [
            {
                "type": "TAG",
                "location": [0, 0, 0],
                "rotation_euler": [0, 0, 0],
                "properties": {"tag_family": "test_fam", "tag_id": 1, "tag_size": 0.1},
            }
        ],
        "cameras": [
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
                "intrinsics": {"resolution": [100, 100]},
            }
        ],
    }

    try:
        with ZmqHostClient(port=port) as client:
            # 1. Test RESET
            resp = client.send_command(CommandType.RESET)
            assert resp.status == ResponseStatus.SUCCESS

            # 2. Test RENDER
            resp = client.send_command(
                CommandType.RENDER,
                payload={
                    "recipe": recipe,
                    "output_dir": str(output_dir),
                    "renderer_mode": "cycles",
                    "skip_visibility": True,
                },
            )
            assert resp.status == ResponseStatus.SUCCESS
            assert "Rendered scene 42" in resp.message

            # Verify some output exists
            assert (output_dir / "images" / "scene_0042_cam_0000.png").exists()
            assert (output_dir / "tags_shard_main.csv").exists()

            # 3. Test SHUTDOWN
            client.send_command(CommandType.SHUTDOWN)

        server_thread.join(timeout=2.0)

    finally:
        server.stop()
