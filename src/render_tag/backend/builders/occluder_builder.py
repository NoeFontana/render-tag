from typing import Any

from render_tag.backend.assets import create_occluder_primitive
from render_tag.core.schema.recipe import ObjectRecipe

from .registry import register_builder


@register_builder("OCCLUDER")
class OccluderBuilder:
    """Builder for shadow-casting occluder primitives (rod/leaf/post)."""

    def build(self, recipe: ObjectRecipe) -> list[Any]:
        props = recipe.properties
        obj = create_occluder_primitive(
            shape=props.get("shape", "rod"),
            width_m=float(props.get("width_m", 0.003)),
            length_m=float(props.get("length_m", 0.15)),
            albedo=float(props.get("albedo", 0.05)),
            roughness=float(props.get("roughness", 0.9)),
        )
        obj.set_location(list(recipe.location))
        if recipe.rotation_euler:
            obj.set_rotation_euler(list(recipe.rotation_euler))
        return [obj]
