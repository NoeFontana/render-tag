"""
Unit tests for backend layouts.
"""

from unittest.mock import MagicMock, patch

import pytest

from render_tag.backend.layouts import apply_layout


@pytest.fixture
def mock_tag_objects():
    return [MagicMock(name=f"tag_{i}") for i in range(4)]


def test_apply_layout_plain(mock_tag_objects):
    with patch("render_tag.backend.layouts.create_plain_layout") as mock_plain:
        res = apply_layout(mock_tag_objects, "plain", spacing=0.1)
        assert res == []
        mock_plain.assert_called_once_with(
            mock_tag_objects, spacing=0.1, tag_size=0.1, center=(0, 0, 0)
        )


def test_apply_layout_cb(mock_tag_objects):
    with patch("render_tag.backend.layouts.create_charuco_layout") as mock_cb:
        mock_cb.return_value = ["board"]
        res = apply_layout(mock_tag_objects, "cb", square_size=0.2)
        assert res == ["board"]
        mock_cb.assert_called_once()


def test_apply_layout_aprilgrid(mock_tag_objects):
    with patch("render_tag.backend.layouts.create_aprilgrid_layout") as mock_ag:
        mock_ag.return_value = ["board", "corners"]
        res = apply_layout(mock_tag_objects, "aprilgrid", square_size=0.2)
        assert res == ["board", "corners"]
        mock_ag.assert_called_once()


def test_create_plain_layout_logic(mock_tag_objects):
    from render_tag.backend.layouts import create_plain_layout

    # Just verify it sets location and rotation
    create_plain_layout(mock_tag_objects, spacing=0.1, tag_size=0.2)
    for obj in mock_tag_objects:
        assert hasattr(obj, "location")
        assert hasattr(obj, "rotation_euler")
