from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from render_tag.backend.scene import create_board_plane


@patch("render_tag.backend.scene.global_pool")
@patch("render_tag.backend.scene.bridge")
def test_create_board_plane_does_not_persist_transformation(mock_bridge, mock_global_pool):
    """
    Test that create_board_plane DOES NOT call persist_transformation_into_mesh.
    This ensures the object's base mesh remains 2x2 so it can be safely reused from the pool.
    """
    mock_board = MagicMock()
    mock_global_pool.get_mesh_object.return_value = mock_board

    # Setup material mock to avoid errors
    mock_bridge.bpy.data.materials.new.return_value = MagicMock()

    # ACT
    create_board_plane(width=0.5, height=0.3, texture_path="fake.png")

    # VERIFY
    # 1. set_scale should be called with [width/2, height/2, 1]
    mock_board.set_scale.assert_called_with([0.25, 0.15, 1])

    # 2. persist_transformation_into_mesh should NOT be called
    mock_board.persist_transformation_into_mesh.assert_not_called()


@patch("render_tag.backend.scene.global_pool")
@patch("render_tag.backend.scene.bridge")
def test_create_board_plane_loads_board_texture_with_string_path(mock_bridge, mock_global_pool):
    mock_board = MagicMock()
    mock_global_pool.get_mesh_object.return_value = mock_board

    mock_material = MagicMock()
    mock_bridge.bpy.data.materials.new.return_value = mock_material
    mock_bridge.bpy.data.images.load.return_value = MagicMock()

    texture_path = Path("/tmp/board_texture.png")

    create_board_plane(width=0.5, height=0.3, texture_path=texture_path)

    mock_bridge.bpy.data.images.load.assert_called_once_with(str(texture_path))
