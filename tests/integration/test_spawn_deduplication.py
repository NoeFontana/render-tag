from __future__ import annotations

from unittest.mock import patch

from render_tag.backend.engine import RenderFacade


@patch("render_tag.backend.engine.create_tag_plane")
@patch("render_tag.backend.engine.create_board_plane")
@patch("render_tag.backend.engine.bridge")
def test_spawn_objects_deduplication(mock_bridge, mock_create_board, mock_create_tag):
    """
    Test that spawn_objects suppresses individual TAGs when a BOARD is present
    with a composite texture.
    """
    renderer = RenderFacade()

    # Mock recipes
    object_recipes = [
        {
            "type": "BOARD",
            "name": "Board_Background",
            "location": [0, 0, 0],
            "rotation_euler": [0, 0, 0],
            "scale": [0.5, 0.5, 1],
            "texture_path": "board_texture.png",
            "board": {"type": "charuco", "rows": 2, "cols": 2, "marker_size": 0.08},
        },
        {
            "type": "TAG",
            "name": "Tag_0",
            "location": [0, 0, 0],
            "properties": {"tag_id": 1, "tag_family": "tag36h11", "tag_size": 0.08},
        },
    ]

    # ACT
    renderer.spawn_objects(object_recipes)

    # VERIFY
    # Board should be created
    mock_create_board.assert_called_once()

    # Tag SHOULD NOT be created (currently this will FAIL because it is created)
    mock_create_tag.assert_not_called()
