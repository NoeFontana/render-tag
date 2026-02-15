"""
Unit tests for backend layouts.
"""

from unittest.mock import MagicMock, patch

import pytest

from render_tag.backend.layouts import arrange_scene


@pytest.fixture
def mock_tag_objects():
    tags = [MagicMock(name=f"tag_{i}") for i in range(4)]
    for t in tags:
        t.set_location = MagicMock()
        t.set_rotation_euler = MagicMock()
        t.enable_rigidbody = MagicMock()
    return tags


def test_arrange_scene_scatter(mock_tag_objects):
    """Test dispatch to ScatterLayoutStrategy."""
    config = {"drop_height": 2.0, "scatter_radius": 1.0}

    with patch("render_tag.backend.layouts.ScatterLayoutStrategy.arrange") as mock_arrange:
        arrange_scene(mock_tag_objects, "scatter", config)
        mock_arrange.assert_called_once_with(mock_tag_objects, config)


def test_arrange_scene_flying(mock_tag_objects):
    """Test dispatch to FlyingLayoutStrategy."""
    config = {"volume_size": 5.0}

    with patch("render_tag.backend.layouts.FlyingLayoutStrategy.arrange") as mock_arrange:
        arrange_scene(mock_tag_objects, "flying", config)
        mock_arrange.assert_called_once_with(mock_tag_objects, config)


def test_arrange_scene_fallback(mock_tag_objects):
    """Test fallback to scatter for unknown layout types."""
    config = {}

    with patch("render_tag.backend.layouts.ScatterLayoutStrategy.arrange") as mock_arrange:
        arrange_scene(mock_tag_objects, "unknown_layout", config)
        mock_arrange.assert_called_once_with(mock_tag_objects, config)
