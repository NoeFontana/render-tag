import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock blenderproc and bpy BEFORE importing modules that use them
sys.modules["blenderproc"] = MagicMock()
sys.modules["bpy"] = MagicMock()

# Now import the module under test
from render_tag.scripts import compositor  # noqa: E402


class TestCompositor:
    @pytest.fixture
    def mock_dependencies(self):
        with (
            patch("render_tag.scripts.compositor.create_tag_plane") as mock_tag,
            patch("render_tag.scripts.compositor.apply_layout") as mock_layout,
            patch("render_tag.scripts.compositor.create_board") as mock_board,
            patch("render_tag.scripts.compositor.create_floor") as mock_floor,
            patch("render_tag.scripts.compositor.create_flying_layout") as mock_flying,
            patch("render_tag.scripts.compositor._setup_physics_for_objects") as mock_physics,
            patch("render_tag.scripts.compositor.get_tag_texture_path") as mock_texture,
        ):
            mock_tag.return_value = MagicMock()
            mock_texture.return_value = "path/to/texture.png"
            yield {
                "tag": mock_tag,
                "layout": mock_layout,
                "board": mock_board,
                "floor": mock_floor,
                "flying": mock_flying,
                "physics": mock_physics,
            }

    def test_compose_scene_plain_auto_calc(self, mock_dependencies):
        """Test composing a plain scene where grid size is auto-calculated."""
        tag_config = {
            "size_meters": 0.1,
            "tags_per_scene": [4, 4],
            "grid_size": [1, 1],
        }  # grid_size small to force recalc
        scenario_config = {"layout": "plain"}
        scene_config = {}
        physics_config = {"drop_height": 0.1}
        tag_families = ["tag36h11"]

        compositor.compose_scene(
            scene_idx=0,
            tag_config=tag_config,
            scenario_config=scenario_config,
            scene_config=scene_config,
            physics_config=physics_config,
            tag_families=tag_families,
        )

        assert mock_dependencies["tag"].call_count == 4
        mock_dependencies["layout"].assert_called_once()
        # Should create board for plain layout
        mock_dependencies["board"].assert_called_once()
        # Should NOT create floor for plain layout (board replaces it)
        mock_dependencies["floor"].assert_not_called()

    def test_compose_scene_charuco(self, mock_dependencies):
        """Test composing a ChArUco scene."""
        tag_config = {"grid_size": [4, 4]}
        scenario_config = {"layout": "cb"}
        scene_config = {}
        physics_config = {}
        tag_families = ["tag36h11"]

        compositor.compose_scene(
            scene_idx=0,
            tag_config=tag_config,
            scenario_config=scenario_config,
            scene_config=scene_config,
            physics_config=physics_config,
            tag_families=tag_families,
        )

        # 4x4 grid = 16 squares. ChArUco has tags in half. (16+1)//2 = 8 tags.
        assert mock_dependencies["tag"].call_count == 8
        mock_dependencies["layout"].assert_called_once()
        mock_dependencies["board"].assert_called_once()

    def test_compose_scene_flying(self, mock_dependencies):
        """Test composing a flying scene."""
        tag_config = {"tags_per_scene": [3, 3]}
        scenario_config = {"flying": True}
        scene_config = {}
        physics_config = {}
        tag_families = ["tag36h11"]

        compositor.compose_scene(
            scene_idx=0,
            tag_config=tag_config,
            scenario_config=scenario_config,
            scene_config=scene_config,
            physics_config=physics_config,
            tag_families=tag_families,
        )

        mock_dependencies["layout"].assert_not_called()
        mock_dependencies["board"].assert_not_called()
        mock_dependencies["flying"].assert_called_once()
