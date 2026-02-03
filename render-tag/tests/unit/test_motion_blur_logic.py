import pytest
from unittest.mock import MagicMock
import sys

# Mock modules before importing backend.camera
# We must do this because backend.camera imports these
sys.modules["blenderproc"] = MagicMock()
sys.modules["bpy"] = MagicMock()
sys.modules["mathutils"] = MagicMock()

def test_setup_motion_blur_exists():
    """Test that setup_motion_blur function exists and is callable."""
    from render_tag.backend.camera import setup_motion_blur
    assert callable(setup_motion_blur)
