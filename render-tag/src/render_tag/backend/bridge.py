"""
Centralized provider for Blender and BlenderProc dependencies.

This module acts as a Service Locator/Bridge that automatically serves
either the real Blender APIs or high-fidelity mocks based on the environment.
"""

import os
import sys
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class BlenderBridge:
    """
    Singleton provider for Blender-related modules.
    """
    _instance: Optional['BlenderBridge'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BlenderBridge, cls).__new__(cls)
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
            
            self.bproc = bproc
            self.bpy = bpy
            self.mathutils = mathutils
            logger.debug("Successfully loaded real Blender/BlenderProc dependencies.")
            
        except (ImportError, RuntimeError):
            # Fallback to Mocks
            logger.info("Blender environment not detected. Serving mock objects.")
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
bpy = bridge.bpy
bproc = bridge.bproc
mathutils = bridge.mathutils
np = bridge.np
