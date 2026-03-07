from __future__ import annotations

from unittest.mock import MagicMock, patch

from render_tag.backend.scene import create_board_plane


@patch("render_tag.backend.scene.bridge")
def test_create_board_plane_persists_transformation(mock_bridge):
    """
    Test that create_board_plane calls persist_transformation_into_mesh.
    This ensures the Blender object ends up with a [1,1,1] scale.
    """
    mock_board = MagicMock()
    mock_bridge.bproc.object.create_primitive.return_value = mock_board

    # Setup material mock to avoid errors
    mock_bridge.bpy.data.materials.new.return_value = MagicMock()

    # ACT
    create_board_plane(width=0.5, height=0.3, texture_path="fake.png")

    # VERIFY
    # 1. set_scale should be called with [width/2, height/2, 1]
    mock_board.set_scale.assert_called_with([0.25, 0.15, 1])

    # 2. persist_transformation_into_mesh should be called
    mock_board.persist_transformation_into_mesh.assert_called_once()

    # Note: In a real Blender environment, after persist_transformation_into_mesh,
    # the object scale property in Blender becomes [1,1,1].
    # Our mock doesn't simulate this state change unless we program it to.
    # But for the purpose of the "failing test" in the plan,
    # if the call was MISSING, this test would fail.
