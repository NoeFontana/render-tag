"""Sunset-metadata enforcement for ``schema/legacy/field_map.LEGACY_FIELDS``.

Every entry in the legacy field-map carries a ``removed_in`` package-version
deadline. When the current package version reaches that deadline, the entry
must be gone (the deprecated field has had its removal window; the table row
and its transform code should be deleted).

This test fails the build rather than silently letting old shims accumulate.
If the build breaks here, the right fix is almost always to remove the
entry — extend the deadline only when there's a concrete reason the field
can't be dropped yet.
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

from render_tag.core.schema.legacy.field_map import LEGACY_FIELDS

_PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def _read_pyproject_version() -> str:
    """Extract the top-level package version from pyproject.toml.

    We read the file directly rather than importing ``render_tag.__version__``
    because the version is dynamic (populated by hatch at build time) and not
    always available in editable installs.
    """
    text = _PYPROJECT.read_text()
    match = re.search(r'(?m)^version\s*=\s*"(?P<version>[^"]+)"', text)
    assert match, 'Could not find `version = "..."` in pyproject.toml'
    return match.group("version")


def test_no_overdue_legacy_entries():
    pkg_version = Version(_read_pyproject_version())
    overdue = [entry for entry in LEGACY_FIELDS if Version(entry.removed_in) <= pkg_version]
    assert not overdue, (
        f"Package version {pkg_version} has reached removed_in for: "
        + ", ".join(f"{e.path} (removed_in={e.removed_in})" for e in overdue)
        + ". Delete these entries from LEGACY_FIELDS and their transform helpers, "
        "or extend the deadline with a code comment explaining why."
    )


def test_since_precedes_removed_in():
    for entry in LEGACY_FIELDS:
        assert Version(entry.since) < Version(entry.removed_in), (
            f"{entry.path}: since={entry.since} must precede removed_in={entry.removed_in}"
        )
