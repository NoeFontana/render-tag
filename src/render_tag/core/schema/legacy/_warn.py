"""Shared deprecation-warning helper for the ACL.

Used by both the migration chain (when legacy fields influence a version hop)
and the field_map module (when a deprecated field is rewritten). Keeping the
helper here lets both callers emit identical, user-facing warnings.
"""

from __future__ import annotations

import warnings


def warn_legacy(field: str, replacement: str) -> None:
    """Emit a DeprecationWarning for a legacy field rewritten by the ACL.

    The deadline for each field lives in ``field_map.LEGACY_FIELDS`` as
    ``removed_in`` (package version). A shared message keeps the user-facing
    guidance uniform — ``render-tag config migrate`` rewrites everything.
    """
    warnings.warn(
        f"Legacy config field {field!r} is deprecated; use {replacement!r}. "
        f"Run `render-tag config migrate <path> --write` to upgrade your config.",
        DeprecationWarning,
        stacklevel=3,
    )
