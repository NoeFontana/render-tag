from typing import Any

from render_tag.backend.assets import create_occluder_primitive
from render_tag.core.schema.recipe import ObjectRecipe

from .registry import register_builder


@register_builder("OCCLUDER")
class OccluderBuilder:
    """Builder for shadow-casting occluder primitives (rod/leaf/post)."""

    def build(self, recipe: ObjectRecipe) -> list[Any]:
        obj = create_occluder_primitive(recipe.properties)
        obj.set_location(list(recipe.location))
        if recipe.rotation_euler:
            obj.set_rotation_euler(list(recipe.rotation_euler))
        return [obj]
