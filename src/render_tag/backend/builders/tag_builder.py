
from pathlib import Path
from typing import Any

from render_tag.backend.assets import create_tag_plane
from render_tag.core.schema.recipe import ObjectRecipe

from .registry import register_builder


@register_builder("TAG")
class TagBuilder:
    """Builder for individual AprilTag assets."""

    def build(self, recipe: ObjectRecipe) -> list[Any]:
        """
        Creates a single AprilTag plane, configures materials, and attaches metadata.
        """
        props = recipe.properties
        texture_path = recipe.texture_path
        
        tag_obj = create_tag_plane(
            props["tag_size"],
            Path(texture_path) if texture_path else None,
            props["tag_family"],
            tag_id=props["tag_id"],
            margin_bits=props.get("margin_bits", 0),
            material_config=recipe.material,
        )
        
        # Set Blender object properties
        tag_obj.blender_obj["pass_index"] = props["tag_id"] + 1
        tag_obj.set_location(recipe.location)
        
        if recipe.rotation_euler:
            tag_obj.set_rotation_euler(recipe.rotation_euler)
            
        # Attach Metadata
        if recipe.keypoints_3d:
            tag_obj.blender_obj["keypoints_3d"] = recipe.keypoints_3d
            
        if recipe.forward_axis:
            tag_obj.blender_obj["forward_axis"] = recipe.forward_axis
            
        return [tag_obj]
