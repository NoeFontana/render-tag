from render_tag.backend.worker_server import ZmqBackendServer
from render_tag.core.schema.hot_loop import Command, CommandType, ResponseStatus


def test_hot_loop_end_to_end(tmp_path, port_generator, stabilized_bridge):
    """
    Staff Engineer: Verify orchestration logic and backend execution flow 
    synchronously using port_generator and stabilized bridge.
    """
    output_dir = tmp_path / "output"
    server = ZmqBackendServer(port=port_generator(), mock=True)

    # 1. Create a dummy recipe
    recipe = {
        "scene_id": 0,
        "world": {},
        "objects": [],
        "cameras": [
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
                "intrinsics": {"resolution": [100, 100]},
            }
        ],
    }

    # 2. Execute directly via server command handler
    # This verifies the Command -> Response logic and the execute_recipe implementation
    cmd = Command(
        command_type=CommandType.RENDER,
        request_id="test-shard-req",
        payload={
            "recipe": recipe,
            "output_dir": str(output_dir),
            "renderer_mode": "cycles",
            "skip_visibility": True
        }
    )    
    resp = server._handle_command(cmd)
    assert resp.status == ResponseStatus.SUCCESS

    # 3. Verify output
    assert (output_dir / "images" / "scene_0000_cam_0000.png").exists()
