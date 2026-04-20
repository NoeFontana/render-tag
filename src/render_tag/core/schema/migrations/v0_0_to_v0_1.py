"""v0.0 -> v0.1: add mandatory version field.

Before v0.1, configs had no explicit version marker. This migration stamps
``version: "0.1"`` on the dict so downstream tooling can identify it. No
other fields change.
"""

from __future__ import annotations

from typing import Any

FROM_VERSION = "0.0"
TO_VERSION = "0.1"


def apply(data: dict[str, Any]) -> dict[str, Any]:
    upgraded = data.copy()
    upgraded["version"] = TO_VERSION
    return upgraded
