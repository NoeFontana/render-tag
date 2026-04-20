"""Flat-config legacy shim.

Pre-versioning configs stored all fields at the top level
(``resolution``, ``samples``, ``tag_family``, ``intent``, ``seed``, ...). The
nested schema introduced in v0.0 groups them into sections. This module
detects the flat shape and rewrites it, so the migration chain downstream can
assume the nested structure.

Runs before the versioned migrations in ``adapt_config``.
"""

from __future__ import annotations

from typing import Any

_FLAT_INDICATORS = frozenset({"resolution", "samples", "tag_family", "intent", "seed"})

_KEY_MAP: dict[str, tuple[str, str | None]] = {
    "resolution": ("camera", "resolution"),
    "samples": ("camera", "samples_per_scene"),
    "tag_family": ("tag", "family"),
    "lighting": ("scene", "lighting"),
    "physics": ("physics", None),  # None = copy whole dict
    "output_dir": ("dataset", "output_dir"),
    "intent": ("dataset", "intent"),
    "num_scenes": ("dataset", "num_scenes"),
    "seed": ("dataset", "seed"),
}


def is_flat(data: dict[str, Any]) -> bool:
    """True when `data` looks like a pre-versioning flat config."""
    return any(k in data for k in _FLAT_INDICATORS) and "dataset" not in data


def detect_and_convert(data: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a flat config into the nested shape. No-op on nested configs."""
    if not is_flat(data):
        return data
    return _convert(data)


def _convert(flat: dict[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {
        "dataset": {},
        "camera": {},
        "tag": {},
        "scene": {},
        "physics": {},
        "scenario": {},
    }

    for flat_key, (section, nested_key) in _KEY_MAP.items():
        if flat_key not in flat:
            continue
        if section not in nested:
            nested[section] = {}
        if nested_key:
            nested[section][nested_key] = flat[flat_key]
        else:
            nested[section] = flat[flat_key]

    if "backgrounds" in flat:
        bg = flat["backgrounds"]
        if "hdri_path" in bg:
            nested["scene"]["background_hdri"] = bg["hdri_path"]
        if "texture_dir" in bg:
            nested["scene"]["texture_dir"] = bg["texture_dir"]

    return nested
