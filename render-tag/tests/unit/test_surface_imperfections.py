import pytest
from unittest.mock import MagicMock
import sys

# Mock Blender
sys.modules["bpy"] = MagicMock()
sys.modules["blenderproc"] = MagicMock()

def test_config_exists():
    from render_tag.schema import TagSurfaceConfig
    cfg = TagSurfaceConfig(scratches=0.5, dust=0.2)
    assert cfg.scratches == 0.5

def test_apply_imperfections_exists():
    from render_tag.backend.assets import apply_surface_imperfections
    assert callable(apply_surface_imperfections)
