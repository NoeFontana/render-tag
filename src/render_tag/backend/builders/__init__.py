
from .interface import AssetBuilder
from .registry import AssetRegistry, register_builder

# Trigger automatic registration of concrete builders
from . import board_builder, null_builder, tag_builder

__all__ = ["AssetBuilder", "AssetRegistry", "register_builder"]
