"""Preset registry primitives.

A ``Preset`` is a named, pure factory of a partial override dict. Presets
are registered via the ``@register_preset`` decorator on module import and
looked up by the ACL's preset-expansion pass.

Names are forced into a dotted ``category.name`` grammar so the CLI can group
presets by category and so collisions stay visible.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_OverrideFn = Callable[[], dict[str, Any]]
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Preset:
    """One registered preset.

    Attributes:
        name: Dotted identifier, ``category.name``.
        description: One-line user-facing summary (shown by ``preset list``).
        version: Semver string for the preset itself; bumping it is a
            convention — preset content drives the job hash, not this field.
        override: Zero-arg callable returning the override dict. Must be
            pure: called multiple times per resolution.
    """

    name: str
    description: str
    version: str
    override: _OverrideFn


class PresetRegistry:
    """Holds ``Preset`` instances keyed by name.

    Registration is one-way: duplicates raise. Lookup raises ``KeyError`` on
    missing names so callers surface the typo in the CLI message.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, Preset] = {}

    def register(self, preset: Preset) -> None:
        if not _NAME_RE.match(preset.name):
            raise ValueError(
                f"Invalid preset name {preset.name!r}: must match "
                f"'category.name' (lowercase, underscores allowed, one dot)."
            )
        if preset.name in self._by_name:
            raise ValueError(f"Preset {preset.name!r} is already registered.")
        self._by_name[preset.name] = preset

    def get(self, name: str) -> Preset:
        try:
            return self._by_name[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._by_name)) or "(none)"
            raise KeyError(f"Unknown preset {name!r}. Available: {available}") from exc

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def by_category(self) -> dict[str, list[Preset]]:
        grouped: dict[str, list[Preset]] = {}
        for name in sorted(self._by_name):
            category = name.split(".", 1)[0]
            grouped.setdefault(category, []).append(self._by_name[name])
        return grouped


default_registry = PresetRegistry()


def register_preset(
    *,
    name: str,
    description: str,
    version: str = "1.0",
    registry: PresetRegistry | None = None,
) -> Callable[[_OverrideFn], _OverrideFn]:
    """Register a preset on import.

    The decorated function takes no arguments and returns the override dict.
    The function is kept importable after decoration so tests can call it
    directly.
    """
    target = registry if registry is not None else default_registry

    def decorator(fn: _OverrideFn) -> _OverrideFn:
        target.register(Preset(name=name, description=description, version=version, override=fn))
        return fn

    return decorator
