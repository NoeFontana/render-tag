"""
Centralized provider for Blender and BlenderProc dependencies.

This module acts as a Service Locator/Bridge that automatically serves
either the real Blender APIs or high-fidelity mocks based on the environment.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import blenderproc
    import bpy
    import mathutils
    import numpy as np
    from bpy.types import Context, Object, Scene
    from mathutils import Matrix, Vector

logger = logging.getLogger(__name__)


class BlenderBridge:
    """
    Singleton provider for Blender-related modules.
    """

    _instance: Optional[BlenderBridge] = None

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

            try:
                from tests.mocks import blender_api as bpy_mock
                from tests.mocks import blenderproc_api as bproc_mock
            except ImportError:
                # If bootstrap hasn't run or is in a weird state, 
                # we might need to manually help it find tests if we are in a dev flow
                # but bootstrap.py should handle .venv which should include the project root.
                # If still not found, we do a last-ditch effort.
                from pathlib import Path
                project_root = str(Path(__file__).resolve().parents[3])
                if project_root not in sys.path:
                    sys.path.append(project_root)
                from tests.mocks import blender_api as bpy_mock
                from tests.mocks import blenderproc_api as bproc_mock

            self.bpy = bpy_mock
            self.bproc = bproc_mock
            # mathutils is harder to mock fully, but we can provide stubs if needed
            self.mathutils = None

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
