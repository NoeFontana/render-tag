"""Preset-expansion pass for the Anti-Corruption Layer.

Runs after ``field_map.apply_all`` and before Pydantic validation. Consumes
the top-level ``presets: [...]`` key, composes each preset's override dict
left-to-right, then overlays the user's own (legacy-rewritten) dict on top
so explicit user values win.

See ``docs/guide.md`` (Presets section) and
``src/render_tag/core/schema_adapter.py`` for how this slots into the ACL.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.logging import get_logger
from render_tag.core.merge import deep_merge, merge_all
from render_tag.core.presets.base import PresetRegistry, default_registry

logger = get_logger(__name__)


def append_cli_presets(data: dict[str, Any], cli_presets: list[str] | None) -> dict[str, Any]:
    """Append CLI preset names to ``data['presets']`` in place, preserving YAML order.

    Later entries compose last, so CLI flags always win over YAML list entries.
    """
    if not cli_presets:
        return data
    existing = data.get("presets")
    if existing is None:
        data["presets"] = list(cli_presets)
    elif isinstance(existing, list):
        data["presets"] = [*existing, *cli_presets]
    else:
        raise ValueError("Top-level `presets` must be a list, e.g. `presets: [lighting.factory]`.")
    return data


def expand(
    data: dict[str, Any],
    registry: PresetRegistry | None = None,
) -> dict[str, Any]:
    """Expand ``data['presets']`` into overrides, then overlay user values.

    Returns a new dict. Leaves the ``presets`` key populated on the output so
    downstream Pydantic validation records the applied preset names on
    ``GenConfig.presets`` (informational).

    If no ``presets`` key is present, returns ``data`` unchanged.
    """
    reg = registry if registry is not None else default_registry
    raw_names = data.get("presets")
    if not raw_names:
        return data
    if not isinstance(raw_names, list):
        raise ValueError(
            "Top-level `presets` must be a list, e.g. `presets: [lighting.factory]`; "
            f"got {type(raw_names).__name__}."
        )

    names = [str(n) for n in raw_names]
    preset_layers = [reg.get(n).override() for n in names]
    composed = merge_all(preset_layers)

    user_layer = {k: v for k, v in data.items() if k != "presets"}
    result = deep_merge(composed, user_layer)
    result["presets"] = names
    logger.debug("Applied presets: %s", names)
    return result
