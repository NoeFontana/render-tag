"""
Centralized provider for Blender and BlenderProc dependencies.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BlenderBridge:
    """
    Singleton provider for Blender-related modules.
    Acts as a Service Locator that is explicitly initialized.
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
        self._initialized = True

    def stabilize(self, bproc_module: Any = None, bpy_module: Any = None, math_module: Any = None):
        """
        Explicitly set the dependencies.
        If not provided, attempts to import real Blender/BlenderProc.
        """
        # 1. Handle NumPy
        if not self.np:
            try:
                import numpy as np

                self.np = np
            except ImportError:
                pass

        # 2. Use provided modules if any
        if bproc_module or bpy_module:
            self.bproc = bproc_module
            self.bpy = bpy_module
            self.mathutils = math_module
            logger.info("BlenderBridge stabilized with provided dependencies.")
            return

        # 3. Fallback: Attempt discovery of real Blender environment
        try:
            import blenderproc as bproc
            import bpy
            import mathutils

            # STUBS CHECK: fake-bpy-module does not have bpy.app
            if hasattr(bpy, "app"):
                self.bproc = bproc
                self.bpy = bpy
                self.mathutils = mathutils
                logger.info("BlenderBridge stabilized with real Blender environment.")
                return
        except (ImportError, RuntimeError):
            pass

        # 4. Final Fallback: Attempt discovery of internal mocks
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

# Late-binding accessors - these will be None until bridge.stabilize() is called
# but modules that 'from bridge import bpy' will get our proxy attributes if we used them.
# For simplicity, we encourage 'from bridge import bridge' and then 'bridge.bpy'.


def get_bpy():
    return bridge.bpy


def get_bproc():
    return bridge.bproc


def get_mathutils():
    return bridge.mathutils
