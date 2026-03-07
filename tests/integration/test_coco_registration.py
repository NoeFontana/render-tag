from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from render_tag.backend.engine import _setup_scene, RenderContext


@patch("render_tag.backend.engine.RenderFacade")
@patch("render_tag.backend.engine.bridge")
def test_setup_scene_coco_registration_boards(mock_bridge, mock_facade_class):
    """
    Test that _setup_scene registers the specific tag family of a BOARD
    to the COCO writer, not just 'calibration_board'.
    """
    mock_facade = mock_facade_class.return_value
    
    # Mock a BOARD object spawned by renderer
    mock_board = MagicMock()
    mock_board.blender_obj = {
        "type": "BOARD",
        "tag_family": "calibration_board",
        "board": '{"type": "charuco", "dictionary": "tag36h11", "rows": 2, "cols": 2}'
    }
    
    mock_facade.spawn_objects.return_value = [mock_board]
    
    ctx = MagicMock(spec=RenderContext)
    ctx.coco_writer = MagicMock()
    ctx.renderer_mode = "cycles"
    
    recipe = {
        "scene_id": 0,
        "objects": [
            {
                "type": "BOARD",
                "board": {"dictionary": "tag36h11"}
            }
        ]
    }
    
    scene_logger = MagicMock()
    
    # ACT
    _setup_scene(recipe, ctx, scene_logger)
    
    # VERIFY
    # 1. Should still register the main family property
    ctx.coco_writer.add_category.assert_any_call("calibration_board")
    
    # 2. SHOULD ALSO register the specific dictionary (currently FAILS)
    ctx.coco_writer.add_category.assert_any_call("tag36h11")
