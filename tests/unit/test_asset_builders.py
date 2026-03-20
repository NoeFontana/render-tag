
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

def test_protocol_compliance():
    # This is a static check mainly, but we can verify it at runtime with
    # isinstance if using runtime_checkable
    pass
