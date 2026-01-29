"""
Pytest configuration for render-tag.

This file sets up the test environment by injecting mocks for Blender modules
BEFORE any tests run or imports happen.
"""

import sys
import types
from pathlib import Path

import pytest

# Add src to pythonpath so we can import modules under test
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# --- MOCK INJECTION START ---
# We must inject mocks BEFORE any test collection happens,
# because test files import modules that import blenderproc.

# Import our mocks
from tests.mocks import blender_api, blenderproc_api  # noqa: E402

# Inject them into sys.modules
sys.modules["bpy"] = blender_api
sys.modules["blenderproc"] = blenderproc_api

# Mock mathutils
if "mathutils" not in sys.modules:
    from typing import Any

    mathutils: Any = types.ModuleType("mathutils")
    mathutils.Matrix = lambda x=None: x if x is not None else []
    mathutils.Vector = lambda x=None: x
    sys.modules["mathutils"] = mathutils
# --- MOCK INJECTION END ---


@pytest.fixture(scope="session")
def mock_blender_environment():
    """
    Fixture to ensure mocks are present (redundant but explicit).
    """
    # Already done at top level
    yield
