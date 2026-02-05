import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Mock bpy/bproc for host-side tests
with patch("render_tag.backend.scene.bpy", create=True) as mock_bpy:
    with patch("render_tag.backend.scene.bproc", create=True) as mock_bproc:
        from render_tag.backend.scene import setup_background

@patch("pathlib.Path.exists", return_value=True)
def test_setup_background_lazy_loading(mock_exists):
    """Verify that setup_background avoids redundant reloads."""
    mock_bpy = MagicMock()
    mock_bproc = MagicMock()
    
    # Simulate a World with a Background node
    world = mock_bpy.context.scene.world
    world.use_nodes = True
    
    env_node = MagicMock()
    env_node.image.filepath = "old_studio.exr"
    world.node_tree.nodes = {
        "Environment Texture": env_node
    }
    
    with patch("render_tag.backend.scene.bpy", mock_bpy):
        with patch("render_tag.backend.scene.bproc", mock_bproc):
            # 1. Load SAME HDRI
            setup_background(Path("old_studio.exr"))
            # Should NOT call bproc setup
            assert mock_bproc.world.set_world_background_hdr_img.call_count == 0
            
            # 2. Load DIFFERENT HDRI
            setup_background(Path("new_warehouse.exr"))
            # Should call bproc setup
            assert mock_bproc.world.set_world_background_hdr_img.called
            assert mock_bproc.world.set_world_background_hdr_img.call_args[0][0] == "new_warehouse.exr"