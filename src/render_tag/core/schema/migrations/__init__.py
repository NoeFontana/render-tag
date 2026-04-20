"""Versioned schema migrations.

Each migration is a module named ``v{X}_{Y}_to_v{A}_{B}.py`` exposing
``FROM_VERSION``, ``TO_VERSION``, and ``apply(data) -> data``. The registry is
built by discovering those modules, indexing by ``FROM_VERSION``, and
validating at import time that the chain is gap-free from ``"0.0"`` to
``CURRENT_SCHEMA_VERSION``.

The one-way-door rule: never edit a migration module after it ships. Configs
produced by earlier versions of the pipeline already exist on disk and in CI
artifacts; they must continue to migrate to the current schema exactly as
they did when they were written. Add a new hop instead.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import Any

from render_tag.core.constants import CURRENT_SCHEMA_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _discover() -> tuple[dict[str, Migration], dict[str, str]]:
    """Scan this package for migration modules and build the registry.

    Returns ``(apply_by_from, to_by_from)`` — both keyed on ``FROM_VERSION``.
    Keeping ``TO_VERSION`` alongside ``apply`` avoids re-importing modules
    during chain validation.
    """
    apply_by_from: dict[str, Migration] = {}
    to_by_from: dict[str, str] = {}
    for module_info in pkgutil.iter_modules(__path__):
        name = module_info.name
        if not name.startswith("v") or "_to_v" not in name:
            continue
        module = importlib.import_module(f"{__name__}.{name}")
        from_version = getattr(module, "FROM_VERSION", None)
        to_version = getattr(module, "TO_VERSION", None)
        apply = getattr(module, "apply", None)
        if not isinstance(from_version, str) or not callable(apply):
            raise ImportError(f"Migration module {name!r} is missing FROM_VERSION or apply()")
        if not isinstance(to_version, str):
            raise ImportError(f"Migration module {name!r} is missing TO_VERSION")
        if from_version in apply_by_from:
            raise ImportError(
                f"Duplicate migration from version {from_version!r} "
                f"(module {name!r} conflicts with another entry)"
            )
        apply_by_from[from_version] = apply
        to_by_from[from_version] = to_version
    return apply_by_from, to_by_from


def _validate_chain(registry: dict[str, Migration], to_by_from: dict[str, str]) -> None:
    """Ensure the chain reaches CURRENT_SCHEMA_VERSION from "0.0" with no gaps."""
    version = "0.0"
    seen: set[str] = set()
    while version != CURRENT_SCHEMA_VERSION:
        if version in seen:
            raise ImportError(f"Migration chain cycles at version {version!r}")
        seen.add(version)
        if version not in registry:
            raise ImportError(
                f"Migration chain is incomplete: no path from {version!r} to "
                f"{CURRENT_SCHEMA_VERSION!r}"
            )
        version = to_by_from[version]


REGISTRY, _TO_BY_FROM = _discover()
_validate_chain(REGISTRY, _TO_BY_FROM)


def get_version(data: dict[str, Any]) -> str:
    """Extract the version string, defaulting to 0.0 for legacy files."""
    return str(data.get("version", "0.0"))


def apply_chain(
    data: dict[str, Any], target_version: str = CURRENT_SCHEMA_VERSION
) -> dict[str, Any]:
    """Sequentially upgrade `data` until it matches `target_version`."""
    current_data = data.copy()
    current_version = get_version(current_data)

    if current_version == target_version:
        return current_data

    if float(current_version) > float(target_version):
        raise ValueError(
            f"Unsupported version: {current_version} (Latest supported: {target_version})"
        )

    while current_version != target_version:
        transform = REGISTRY.get(current_version)
        if transform is None:
            raise ValueError(f"No migration path found from version {current_version}")
        current_data = transform(current_data)
        current_version = get_version(current_data)

    return current_data


__all__ = [
    "REGISTRY",
    "apply_chain",
    "get_version",
]
