"""
Pytest plugin: inject Blender mocks into ``sys.modules``.

Blender's Python modules (``bpy``, ``blenderproc``, ``mathutils``) are not
available in a standard Python interpreter. Many modules under test import
them at module top-level, so the substitute mocks must be installed in
``sys.modules`` *before* any ``render_tag.backend.*`` import happens.

This plugin is registered by the ``pytest_plugins`` variable in
``tests/conftest.py``. Pytest imports listed plugins during startup, before
collection begins. Performing the injection at this module's import time
therefore guarantees the invariant holds for every test.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.nodes import Item


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _PROJECT_ROOT / "src"
for _path in (_SRC_PATH, _PROJECT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def _inject_blender_mocks() -> None:
    """Replace Blender modules in ``sys.modules`` with our mocks."""
    from render_tag.backend.mocks import (
        blender_api,
        blenderproc_api,
        mathutils_api,
    )

    sys.modules["bpy"] = blender_api
    sys.modules["blenderproc"] = blenderproc_api
    sys.modules["mathutils"] = mathutils_api


_inject_blender_mocks()


# --- Marker enforcement ---

_SUBPROCESS_CALL = re.compile(r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\b")
_MONKEYPATCH_SUBPROCESS = re.compile(r"monkeypatch\.setattr\s*\(\s*subprocess\b")


def _strip_comment(line: str) -> str:
    """Drop everything after an unquoted ``#``. Good enough for our scan."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def _only_patched(src: str) -> bool:
    """
    Return True iff every subprocess reference in code (outside comments) is
    a patching statement — either ``patch("subprocess...")``, ``patch.object(subprocess, ...)``,
    or ``monkeypatch.setattr(subprocess, ...)``.

    Tests that *patch* subprocess never actually spawn a child process and
    are safe to run in the fast tier. Tests that call subprocess directly
    are integration tests and must be marked as such.
    """
    for line in src.splitlines():
        if "subprocess" not in line:
            continue
        code = _strip_comment(line)
        has_call = bool(_SUBPROCESS_CALL.search(code))
        has_monkeypatch = bool(_MONKEYPATCH_SUBPROCESS.search(code))
        if not (has_call or has_monkeypatch):
            continue
        if has_monkeypatch or "patch" in code:
            continue
        return False
    return True


_INTEGRATION_DIR = _PROJECT_ROOT / "tests" / "integration"


def pytest_itemcollected(item: Item) -> None:
    """Auto-mark tests under ``tests/integration/`` before any ``-m`` filter runs."""
    fspath = Path(str(item.fspath))
    if _INTEGRATION_DIR in fspath.parents and not item.get_closest_marker("integration"):
        item.add_marker(pytest.mark.integration)


def _is_offender(fspath: Path) -> bool:
    """Does the file call subprocess directly (without patching)?"""
    try:
        src = fspath.read_text()
    except OSError:
        return False
    if not _SUBPROCESS_CALL.search(src):
        return False
    return not _only_patched(src)


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    """
    1. Serialize integration tests onto a single xdist worker.
    2. Reject tests that call subprocess without the ``integration`` marker.
    """
    offenders: list[str] = []
    offender_cache: dict[Path, bool] = {}
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(pytest.mark.xdist_group(name="serial_integration"))
            continue
        fspath = Path(str(item.fspath))
        if fspath not in offender_cache:
            offender_cache[fspath] = _is_offender(fspath)
        if offender_cache[fspath]:
            offenders.append(item.nodeid)
    if offenders:
        listing = "\n".join(f"  - {n}" for n in offenders)
        raise pytest.UsageError(
            f"Tests call subprocess without @pytest.mark.integration:\n{listing}\n\n"
            "Either add the marker, use mock.patch(), or monkeypatch.setattr(subprocess, ...)."
        )
