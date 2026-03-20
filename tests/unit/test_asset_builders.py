
from typing import Any

import pytest

from render_tag.backend.builders.registry import AssetRegistry, register_builder
from render_tag.core.schema.recipe import ObjectRecipe


class MockBuilder:
    def build(self, recipe: ObjectRecipe) -> list[Any]:
        return ["mock_object"]

def test_registry_registration():
    registry = AssetRegistry()
    registry.register("MOCK", MockBuilder())
    
    builder = registry.get_builder("MOCK")
    assert isinstance(builder, MockBuilder)

def test_decorator_registration():
    registry = AssetRegistry()
    
    @register_builder("DECORATED", registry=registry)
    class DecoratedBuilder:
        def build(self, recipe: ObjectRecipe) -> list[Any]:
            return ["decorated_object"]
            
    builder = registry.get_builder("DECORATED")
    assert isinstance(builder, DecoratedBuilder)

def test_registry_build_object():
    registry = AssetRegistry()
    registry.register("MOCK", MockBuilder())
    
    recipe = ObjectRecipe(
        type="MOCK",
        name="test_mock",
        location=[0, 0, 0]
    )
    
    assets = registry.build_object(recipe)
    assert assets == ["mock_object"]

def test_registry_missing_builder():
    registry = AssetRegistry()
    recipe = ObjectRecipe(
        type="MISSING",
        name="test_missing",
        location=[0, 0, 0]
    )
    
    with pytest.raises(KeyError, match="No builder registered for type: MISSING"):
        registry.build_object(recipe)

def test_tag_builder_integration():
    from unittest.mock import MagicMock, patch

    from render_tag.backend.builders.tag_builder import TagBuilder
    
    # Mock ObjectRecipe
    recipe = ObjectRecipe(
        type="TAG",
        name="test_tag",
        location=[1.0, 2.0, 3.0],
        rotation_euler=[0.1, 0.2, 0.3],
        properties={
            "tag_size": 0.16,
            "tag_family": "tag36h11",
            "tag_id": 42,
            "margin_bits": 2
        },
        texture_path="/tmp/test.png",
        material={"roughness": 0.5},
        keypoints_3d=[[0,0,0]],
        forward_axis=[0,0,1,0]
    )
    
    mock_tag_obj = MagicMock()
    mock_tag_obj.blender_obj = {}
    
    patch_path = "render_tag.backend.builders.tag_builder.create_tag_plane"
    with patch(patch_path, return_value=mock_tag_obj) as mock_create:
        builder = TagBuilder()
        assets = builder.build(recipe)
        
        # Verify create_tag_plane call
        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        assert args[0] == 0.16
        assert args[2] == "tag36h11"
        assert kwargs["tag_id"] == 42
        assert kwargs["material_config"] == {"roughness": 0.5}
        
        # Verify object setup
        mock_tag_obj.set_location.assert_called_once_with([1.0, 2.0, 3.0])
        mock_tag_obj.set_rotation_euler.assert_called_once_with([0.1, 0.2, 0.3])
        assert mock_tag_obj.blender_obj["pass_index"] == 43
        assert mock_tag_obj.blender_obj["keypoints_3d"] == [[0,0,0]]
        assert mock_tag_obj.blender_obj["forward_axis"] == [0,0,1,0]
        assert assets == [mock_tag_obj]

def test_board_builder_hi_fi():
    from unittest.mock import MagicMock, patch

    from render_tag.backend.builders.board_builder import CalibrationBoardBuilder
    from render_tag.core.schema.board import BoardConfig
    
    recipe = ObjectRecipe(
        type="BOARD",
        name="test_board",
        location=[0, 0, 0],
        scale=[1, 1, 1],
        texture_path="/tmp/board.png",
        board=BoardConfig(type="aprilgrid", cols=5, rows=4, marker_size=0.08, spacing_ratio=0.5)
    )
    
    mock_board_obj = MagicMock()
    mock_board_obj.blender_obj = {}
    
    patch_path = "render_tag.backend.builders.board_builder.create_board_plane"
    with patch(patch_path, return_value=mock_board_obj) as mock_create:
        builder = CalibrationBoardBuilder()
        assets = builder.build(recipe)
        
        mock_create.assert_called_once()
        # Verify calculated width/height: sqs = 0.08 * 1.5 = 0.12.
        # width = 0.12*5 = 0.6. height = 0.12*4 = 0.48.
        kwargs = mock_create.call_args.kwargs
        assert pytest.approx(kwargs["width"]) == 0.6
        assert pytest.approx(kwargs["height"]) == 0.48
        assert assets == [mock_board_obj]

def test_board_builder_legacy():
    from unittest.mock import MagicMock, patch

    from render_tag.backend.builders.board_builder import CalibrationBoardBuilder
    
    recipe = ObjectRecipe(
        type="BOARD",
        name="test_board_legacy",
        location=[0, 0, 0],
        properties={"cols": 3, "rows": 3, "marker_size": 0.08}
    )
    
    mock_board_obj = MagicMock()
    mock_board_obj.blender_obj = {}
    
    patch_path = "render_tag.backend.builders.board_builder.create_board"
    with patch(patch_path, return_value=mock_board_obj) as mock_create:
        builder = CalibrationBoardBuilder()
        assets = builder.build(recipe)
        
        mock_create.assert_called_once_with(
            3, 3, 0.08, "tag36h11", None, material_config=None
        )
        assert assets == [mock_board_obj]

def test_null_builder():
    from render_tag.backend.builders.null_builder import NullBuilder
    
    recipe = ObjectRecipe(type="NULL", name="test_null", location=[0,0,0])
    builder = NullBuilder()
    assets = builder.build(recipe)
    assert assets == []

def test_protocol_compliance():
    # This is a static check mainly, but we can verify it at runtime with
    # isinstance if using runtime_checkable
    pass
