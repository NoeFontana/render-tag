from unittest.mock import MagicMock, patch

import pytest

from render_tag.backend.engine import RenderFacade
from render_tag.core.schema.recipe import ObjectRecipe


def test_spawn_objects_uses_registry():
    renderer = RenderFacade()

    # Mock ObjectRecipe
    recipe = ObjectRecipe(type="MOCK", name="test", location=[0, 0, 0])

    mock_assets = [MagicMock(name="BlenderObj")]

    # We need to mock the registry to return our mock assets
    with patch("render_tag.backend.engine.default_registry") as mock_registry:
        mock_registry.build_object.return_value = mock_assets

        assets = renderer.spawn_objects([recipe])

        mock_registry.build_object.assert_called_once_with(recipe)
        assert assets == mock_assets


def test_spawn_objects_fail_hard_on_missing_builder():
    renderer = RenderFacade()
    recipe = ObjectRecipe(type="MISSING", name="test", location=[0, 0, 0])

    # default_registry.build_object will raise KeyError if not found
    with patch("render_tag.backend.engine.default_registry") as mock_registry:
        mock_registry.build_object.side_effect = KeyError("No builder")

        with pytest.raises(KeyError):
            renderer.spawn_objects([recipe])
