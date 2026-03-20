
from typing import Any

from render_tag.core.schema.recipe import ObjectRecipe

from .registry import register_builder


@register_builder("NULL")
class NullBuilder:
    """A placeholder builder that returns an empty list of assets."""

    def build(self, recipe: ObjectRecipe) -> list[Any]:
        """Returns an empty list."""
        return []
