from typing import Any, Protocol, runtime_checkable

from render_tag.core.schema.recipe import ObjectRecipe


@runtime_checkable
class AssetBuilder(Protocol):
    """Protocol for classes that build Blender assets from ObjectRecipes."""

    def build(self, recipe: ObjectRecipe) -> list[Any]:
        """
        Translates a configuration into a list of Blender assets.

        Args:
            recipe: The configuration recipe for the object.

        Returns:
            A list of Blender objects/assets (often wrapper objects).
        """
        ...
