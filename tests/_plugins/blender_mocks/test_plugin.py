"""Sanity tests for the blender_mocks plugin.

If the plugin is not loaded, these fail loudly rather than letting downstream
tests produce confusing errors.
"""

from __future__ import annotations

import sys


def test_bpy_is_mocked() -> None:
    from render_tag.backend.mocks import blender_api

    assert sys.modules.get("bpy") is blender_api


def test_blenderproc_is_mocked() -> None:
    from render_tag.backend.mocks import blenderproc_api

    assert sys.modules.get("blenderproc") is blenderproc_api


def test_mathutils_is_mocked() -> None:
    from render_tag.backend.mocks import mathutils_api

    assert sys.modules.get("mathutils") is mathutils_api
