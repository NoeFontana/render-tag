from collections.abc import Callable
from typing import Any, TypeVar

from render_tag.core.schema.recipe import ObjectRecipe

from .interface import AssetBuilder

T = TypeVar("T", bound=type[AssetBuilder])


class AssetRegistry:
    """Registry for AssetBuilders, mapping subject types to their builders."""

    def __init__(self):
        """Initializes an empty registry of builders."""
        self._builders: dict[str, AssetBuilder] = {}

    def register(self, object_type: str, builder: AssetBuilder) -> None:
        """Explicitly register a builder instance for a type.

        Args:
            object_type: The subject type identifier (e.g., 'TAG').
            builder: An instance implementing the AssetBuilder protocol.
        """
        self._builders[object_type.upper()] = builder

    def get_builder(self, object_type: str) -> AssetBuilder:
        """Retrieve a builder for the given type."""
        normalized_type = object_type.upper()
        if normalized_type not in self._builders:
            raise KeyError(f"No builder registered for type: {normalized_type}")
        return self._builders[normalized_type]

    def build_object(self, recipe: ObjectRecipe) -> list[Any]:
        """Look up the builder for the recipe's type and invoke it."""
        builder = self.get_builder(recipe.type)
        return builder.build(recipe)


# Global default registry
default_registry = AssetRegistry()


def register_builder(object_type: str, registry: AssetRegistry | None = None) -> Callable[[T], T]:
    """Decorator to automatically register a builder class.

    Args:
        object_type: The subject type identifier to register (e.g., 'TAG').
        registry: Optional registry instance to use. Defaults to global registry.

    Returns:
        A decorator that instantiates and registers the builder class.
    """
    target_registry = registry or default_registry

    def decorator(cls: T) -> T:
        # Instantiate and register
        target_registry.register(object_type, cls())
        return cls

    return decorator
