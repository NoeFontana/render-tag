from __future__ import annotations

from unittest.mock import MagicMock, patch

from render_tag.backend.engine import RenderFacade
from render_tag.core.schema.recipe import ObjectRecipe


@patch("render_tag.backend.engine.default_registry")
@patch("render_tag.backend.engine.bridge")
def test_spawn_objects_deduplication(mock_bridge, mock_registry):
    """
    Test that spawn_objects suppresses individual TAGs when a BOARD is present
    with a composite texture.
    """
    renderer = RenderFacade()

    # Mock recipes
    object_recipes = [
        ObjectRecipe(
            type="BOARD",
            name="Board_Background",
            location=[0, 0, 0],
            rotation_euler=[0, 0, 0],
            scale=[0.5, 0.5, 1],
            texture_path="board_texture.png",
            board={
                "type": "charuco",
                "rows": 2,
                "cols": 2,
                "marker_size": 0.08,
                "square_size": 0.1,
            },
        ),
        ObjectRecipe(
            type="TAG",
            name="Tag_0",
            location=[0, 0, 0],
            properties={"tag_id": 1, "tag_family": "tag36h11", "tag_size": 0.08},
        ),
    ]

    mock_registry.build_object.return_value = [MagicMock()]

    # ACT
    renderer.spawn_objects(object_recipes)

    # VERIFY
    # Board should be created, Tag SHOULD NOT be created
    mock_registry.build_object.assert_called_once_with(object_recipes[0])
