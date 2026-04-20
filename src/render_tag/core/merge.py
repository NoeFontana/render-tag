"""Deep-merge helpers for composing config override dicts.

Used by the preset pipeline (``core.presets``) and by the experiment
orchestrator. Kept stdlib-only so it can live at the bottom of the import
graph — every layer above ``core`` can depend on it.

Merge rules:

- ``dict`` + ``dict``           → recurse key-by-key
- ``list[str]`` + ``list[str]`` → concatenate, order-preserving dedupe
- ``list[dict]`` + ``list[dict]`` → source replaces wholesale
- other lists (mixed, numeric)  → source replaces wholesale
- scalar / ``None`` / missing   → source replaces (``None`` is an explicit clear)

Inputs are not mutated. Each call returns a fresh dict.
"""

from __future__ import annotations

import copy
from typing import Any


def deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Merge ``source`` into a deep copy of ``target`` and return the result.

    Source values win on scalars. Nested dicts recurse. See module docstring
    for list-handling rules.
    """
    out: dict[str, Any] = copy.deepcopy(target)
    for key, src_val in source.items():
        if key not in out:
            out[key] = copy.deepcopy(src_val)
            continue
        tgt_val = out[key]
        if isinstance(tgt_val, dict) and isinstance(src_val, dict):
            out[key] = deep_merge(tgt_val, src_val)
        elif isinstance(tgt_val, list) and isinstance(src_val, list):
            out[key] = _merge_lists(tgt_val, src_val)
        else:
            out[key] = copy.deepcopy(src_val)
    return out


def merge_all(layers: list[dict[str, Any]]) -> dict[str, Any]:
    """Left-to-right fold: ``merge_all([A, B, C]) == deep_merge(deep_merge(A, B), C)``."""
    result: dict[str, Any] = {}
    for layer in layers:
        result = deep_merge(result, layer)
    return result


def _merge_lists(target: list[Any], source: list[Any]) -> list[Any]:
    if _is_list_of_strings(target) and _is_list_of_strings(source):
        seen: set[str] = set()
        merged: list[str] = []
        for item in (*target, *source):
            if item not in seen:
                merged.append(item)
                seen.add(item)
        return merged
    return copy.deepcopy(source)


def _is_list_of_strings(lst: list[Any]) -> bool:
    return bool(lst) and all(isinstance(x, str) for x in lst)
