"""
Explicit registry for Blender and BlenderProc dependencies.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.logging import get_logger

logger = get_logger(__name__)


class BlenderBridge:
    """
    Registry for Blender-related modules.
    Ensures backend modules can access Blender APIs regardless of the environment.
    """

    _instance: BlenderBridge | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.bpy = None
            cls._instance.bproc = None
            cls._instance.mathutils = None
            cls._instance.np = None
        return cls._instance

    def stabilize(self, bproc_module: Any = None, bpy_module: Any = None, math_module: Any = None):
        """Explicitly set the dependencies or attempt auto-discovery."""
        # 1. Ensure NumPy is available
        try:
            import numpy as np
            self.np = np
        except ImportError:
            pass

        # 2. Use provided modules
        if bproc_module or bpy_module:
            self.bproc = bproc_module
            self.bpy = bpy_module
            self.mathutils = math_module
            logger.info("BlenderBridge stabilized with provided dependencies.")
            return

        # 3. Auto-discovery
        try:
            import blenderproc as bproc
            import bpy
            import mathutils

            # Verify we are in a real Blender environment
            if hasattr(bpy, "app"):
                self.bproc = bproc
                self.bpy = bpy
                self.mathutils = mathutils
                logger.info("BlenderBridge stabilized with real Blender environment.")
                return
        except (ImportError, RuntimeError):
            pass

        # 4. Mock fallback
        try:
            from render_tag.backend.mocks import blender_api as bpy_mock
            from render_tag.backend.mocks import blenderproc_api as bproc_mock
            from render_tag.backend.mocks import mathutils_api as math_mock

            self.bproc = bproc_mock
            self.bpy = bpy_mock
            self.mathutils = math_mock
            logger.info("BlenderBridge stabilized with internal mocks.")
        except ImportError:
            logger.warning("BlenderBridge: Could not find any dependencies or mocks.")


# Singleton instance
bridge = BlenderBridge()
