"""
Centralized provider for Blender and BlenderProc dependencies.

This module acts as a Service Locator/Bridge that automatically serves
either the real Blender APIs or high-fidelity mocks based on the environment.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import bpy
    import mathutils
    import numpy as np

logger = logging.getLogger(__name__)


class BlenderBridge:
    """
    Singleton provider for Blender-related modules.
    """

    _instance: BlenderBridge | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.bpy: Any = None
        self.bproc: Any = None
        self.mathutils: Any = None
        self.np: Any = None

        self._load_dependencies()
        self._initialized = True

    def _load_dependencies(self):
        """Attempts to load real dependencies, falls back to mocks."""

        # 1. Load NumPy (Fundamental)
        try:
            import numpy as np

            self.np = np
        except ImportError:
            logger.warning("NumPy not found. Some geometry math may fail.")
            self.np = None

        # 2. Load Blender/BlenderProc
        try:
            # We try to import blenderproc first as it often enforces the 'blenderproc run' check
            import blenderproc as bproc
            import bpy
            import mathutils

            # STUBS CHECK: fake-bpy-module does not have bpy.app
            if not hasattr(bpy, "app"):
                raise ImportError("Real Blender environment not detected (stubs found instead).")

            self.bproc = bproc
            self.bpy = bpy
            self.mathutils = mathutils
            logger.debug("Successfully loaded real Blender/BlenderProc dependencies.")

        except (ImportError, RuntimeError):
            # Fallback to Mocks
            logger.info("Blender environment not detected. Serving mock objects.")

            # Check if mocks were already injected into sys.modules (via inject_mocks)
            # Staff Engineer: We must differentiate between "injected mocks" and "bad stubs"
            # If the module in sys.modules is the real stub that failed validation, we ignore it.
            if "bpy" in sys.modules and getattr(sys.modules["bpy"], "__mock__", False):
                self.bpy = sys.modules["bpy"]
                self.bproc = sys.modules["blenderproc"]
                if "mathutils" in sys.modules:
                    self.mathutils = sys.modules["mathutils"]
                return

            # Otherwise try to import them (requires project root in path)
            try:
                from tests.mocks import blender_api as bpy_mock
                from tests.mocks import blenderproc_api as bproc_mock
                from tests.mocks import mathutils_api as math_mock

                self.bpy = bpy_mock
                self.bproc = bproc_mock
                self.mathutils = math_mock
            except ImportError:
                # Last resort: ensure project root is in path
                from pathlib import Path

                project_root = str(Path(__file__).resolve().parents[3])
                if project_root not in sys.path:
                    sys.path.append(project_root)

                try:
                    from tests.mocks import blender_api as bpy_mock
                    from tests.mocks import blenderproc_api as bproc_mock
                    from tests.mocks import mathutils_api as math_mock

                    self.bpy = bpy_mock
                    self.bproc = bproc_mock
                    self.mathutils = math_mock
                except ImportError:
                    logger.warning(
                        "Could not load Blender mocks. Some functionality will be limited."
                    )

    def inject_mocks(self, bproc_mock: Any, bpy_mock: Any):
        """Explicitly override dependencies with provided mocks."""
        self.bproc = bproc_mock
        self.bpy = bpy_mock
        logger.debug("Mocks manually injected into BlenderBridge.")


# Singleton accessors for easy importing
bridge = BlenderBridge()
bpy: Any = bridge.bpy
bproc: Any = bridge.bproc
mathutils: Any = bridge.mathutils
np: Any = bridge.np
