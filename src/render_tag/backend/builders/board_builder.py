
from pathlib import Path
from typing import Any

from render_tag.backend.scene import create_board, create_board_plane
from render_tag.core.schema.recipe import ObjectRecipe

from .registry import register_builder


@register_builder("BOARD")
class CalibrationBoardBuilder:
    """Builder for Calibration Board assets (AprilGrid, ChArUco)."""

    def build(self, recipe: ObjectRecipe) -> list[Any]:
        """
        Creates a calibration board plane or procedural board.
        """
        texture_path = recipe.texture_path
        board_cfg = recipe.board
        
        # Robustly handle material config
        mat_cfg = recipe.material
        if hasattr(mat_cfg, "model_dump"):
            mat_cfg = mat_cfg.model_dump()

        if texture_path and board_cfg:
            # Generic High-Fidelity Subject Path (Single Plane)
            cols, rows = board_cfg.cols, board_cfg.rows
            ms = board_cfg.marker_size
            
            if board_cfg.type == "aprilgrid":
                sqs = ms * (1.0 + getattr(board_cfg, "spacing_ratio", 0.0))
            else:
                sqs = getattr(board_cfg, "square_size", ms)
            
            width, height = sqs * cols, sqs * rows

            board_obj = create_board_plane(
                width=width,
                height=height,
                texture_path=Path(texture_path) if texture_path else None,
                material_config=mat_cfg,
            )
            board_obj.blender_obj["tag_family"] = "calibration_board"
            if hasattr(board_cfg, "model_dump_json"):
                board_obj.blender_obj["board"] = board_cfg.model_dump_json()
            board_obj.blender_obj["type"] = "BOARD"
        else:
            # Legacy or procedural board
            props = recipe.properties
            board_obj = create_board(
                cols=props.get("cols", 3),
                rows=props.get("rows", 3),
                square_size=props.get("square_size", 0.1),
                layout_mode=props.get("tag_family", "tag36h11"),
                location=list(recipe.location),
                material_config=mat_cfg,
            )
            # Legacy doesn't always have board_cfg, so we skip board_json for now
            board_obj.blender_obj["type"] = "BOARD"

        # Common setup
        board_obj.set_location(list(recipe.location))
        if recipe.rotation_euler:
            board_obj.set_rotation_euler(list(recipe.rotation_euler))
            
        if recipe.keypoints_3d and isinstance(recipe.keypoints_3d, (list, tuple)):
            board_obj.blender_obj["keypoints_3d"] = [list(kp) for kp in recipe.keypoints_3d if hasattr(kp, "__iter__")]

        if recipe.forward_axis:
            board_obj.blender_obj["forward_axis"] = list(recipe.forward_axis)

        return [board_obj]
