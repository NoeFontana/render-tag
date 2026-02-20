
from render_tag.backend.worker_server import ZmqBackendServer
from render_tag.core.schema.hot_loop import Command, CommandType, ResponseStatus


def test_hot_loop_render_command(tmp_path, port_generator, stabilized_bridge):
    """
    Staff Engineer: Test the hot-loop RENDER logic synchronously.
    Uses port_generator and stabilized_bridge for systematic reliability.
    """
    # Initialize server but don't start its loop
    server = ZmqBackendServer(port=port_generator())
    
    # Staff Engineer: Enforce mock state to prevent pollution from other tests
    import numpy as np

    from render_tag.backend.bridge import bridge
    from render_tag.backend.mocks import blenderproc_api
    
    bridge.bproc = blenderproc_api
    # Ensure render returns valid data
    blenderproc_api.renderer.render = lambda: {
        "colors": [np.ones((100, 100, 3), dtype=np.uint8) * 255],
        "segmentation": [np.zeros((100, 100), dtype=np.uint32)],
    }
    
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

    # 1. Test RESET
    cmd_reset = Command(command_type=CommandType.RESET, request_id="req_1")
    resp = server._handle_command(cmd_reset)
    assert resp.status == ResponseStatus.SUCCESS

    # 2. Test RENDER
    cmd_render = Command(
        command_type=CommandType.RENDER,
        request_id="req_2",
        payload={
            "recipe": recipe,
            "output_dir": str(output_dir),
            "renderer_mode": "cycles",
            "skip_visibility": True,
        },
    )
    
    # This call is synchronous and uses internal mocks
    resp = server._handle_command(cmd_render)
    
    assert resp.status == ResponseStatus.SUCCESS
    assert "Rendered scene 42" in resp.message

    # Verify output exists immediately (no race condition)
    assert (output_dir / "images" / "scene_0042_cam_0000.png").exists()
    assert (output_dir / "tags_shard_main.csv").exists()

    # 3. Test SHUTDOWN
    cmd_shutdown = Command(command_type=CommandType.SHUTDOWN, request_id="req_3")
    resp = server._handle_command(cmd_shutdown)
    assert resp.status == ResponseStatus.SUCCESS
    
    server.stop()
