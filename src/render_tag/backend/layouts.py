"""
Scene layout strategies for render-tag.

Provides a pluggable Strategy Pattern architecture for positioning tags
within a Blender scene using various procedural logic.
"""

import random
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LayoutStrategy(Protocol):
    """Protocol for scene layout strategies."""

    def arrange(self, tag_objects: list[Any], config: dict[str, Any]) -> None:
        """
        Arrange tag objects in the scene according to the strategy.

        Args:
            tag_objects: List of Blender objects to position.
            config: Dictionary of parameters for the layout.
        """
        ...


class ScatterLayoutStrategy:
    """Scatters tags randomly on a floor plane with physics enabled."""

    def arrange(self, tag_objects: list[Any], config: dict[str, Any]) -> None:
        drop_height = config.get("drop_height", 1.5)
        scatter_radius = config.get("scatter_radius", 0.5)

        for tag in tag_objects:
            x = random.uniform(-scatter_radius, scatter_radius)
            y = random.uniform(-scatter_radius, scatter_radius)
            z = drop_height + random.uniform(0, 0.5)

            rx = random.uniform(0, 2 * 3.14159)
            ry = random.uniform(0, 2 * 3.14159)
            rz = random.uniform(0, 2 * 3.14159)

            tag.set_location([x, y, z])
            tag.set_rotation_euler([rx, ry, rz])

            # Enable physics
            tag.enable_rigidbody(
                active=True,
                collision_shape="BOX",
                mass=0.01,
                friction=0.5,
            )


class FlyingLayoutStrategy:
    """Randomly positions tags in a 3D volume (static)."""

    def arrange(self, tag_objects: list[Any], config: dict[str, Any]) -> None:
        volume_size = config.get("volume_size", 2.0)

        for tag in tag_objects:
            x = random.uniform(-volume_size / 2, volume_size / 2)
            y = random.uniform(-volume_size / 2, volume_size / 2)
            z = random.uniform(0.5, volume_size + 0.5)

            rx = random.uniform(0, 2 * 3.14159)
            ry = random.uniform(0, 2 * 3.14159)
            rz = random.uniform(0, 2 * 3.14159)

            tag.set_location([x, y, z])
            tag.set_rotation_euler([rx, ry, rz])
            tag.enable_rigidbody(active=False)


class BoardLayoutStrategy:
    """Arranges tags in a grid on a board (not yet fully implemented as strategy)."""

    def arrange(self, tag_objects: list[Any], config: dict[str, Any]) -> None:
        # Placeholder for complex board logic if needed
        # Currently handled by create_board in scene.py
        pass


class LayoutEngine:
    """Registry and executor for layout strategies."""

    def __init__(self):
        self._strategies: dict[str, LayoutStrategy] = {
            "scatter": ScatterLayoutStrategy(),
            "flying": FlyingLayoutStrategy(),
            "board": BoardLayoutStrategy(),
        }

    def apply_layout(self, tag_objects: list[Any], layout_type: str, config: dict[str, Any]) -> None:
        """Dispatcher that selects and runs the appropriate strategy."""
        strategy = self._strategies.get(layout_type)
        if not strategy:
            # Fallback to scatter
            strategy = self._strategies["scatter"]

        strategy.arrange(tag_objects, config)


# Global engine instance
_engine = LayoutEngine()


def arrange_scene(tag_objects: list[Any], layout_type: str, config: dict[str, Any]) -> None:
    """Entry point for scene arrangement."""
    _engine.apply_layout(tag_objects, layout_type, config)
