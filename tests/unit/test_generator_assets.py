from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from render_tag.generation.scene import Generator
from render_tag.core.config import GenConfig

@pytest.fixture
def mock_asset_provider():
    with patch("render_tag.generation.scene.AssetProvider") as mock:
        provider_instance = mock.return_value
        # Default behavior: just return the path as is (simulating local hit)
        provider_instance.resolve_path.side_effect = lambda x: Path("/mock/assets") / x
        yield provider_instance

@pytest.fixture
def basic_config():
    return GenConfig.model_validate({
        "dataset": {"num_scenes": 1},
        "scene": {
            "background_hdri": "hdri/test.exr",
            "texture_dir": "textures/background"
        },
        "tag": {
            "texture_path": "tags/tag36h11"
        },
        "scenario": {
            "tag_families": ["tag36h11"]
        }
    })

def test_generator_uses_asset_provider_for_hdri(mock_asset_provider, basic_config, tmp_path):
    gen = Generator(basic_config, output_dir=tmp_path)
    scene = gen.generate_scene(0)
    
    # Check if AssetProvider was used for HDRI
    mock_asset_provider.resolve_path.assert_any_call("hdri/test.exr")
    assert scene.world.background_hdri == str(Path("/mock/assets/hdri/test.exr"))

def test_generator_uses_asset_provider_for_textures(mock_asset_provider, basic_config, tmp_path):
    # Setup some mock textures to be picked
    mock_asset_provider.resolve_path.side_effect = lambda x: Path("/mock/assets") / x
    
    # We need to mock the texture listing since it uses .iterdir() on the config path
    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "iterdir", return_value=[Path("textures/background/tex1.png")]):
        gen = Generator(basic_config, output_dir=tmp_path)
        scene = gen.generate_scene(0)
        
        # In generate_scene -> _generate_world_config
        # It picks a random texture from self.textures and resolves it
        mock_asset_provider.resolve_path.assert_any_call("textures/background/tex1.png")
        assert scene.world.texture_path == str(Path("/mock/assets/textures/background/tex1.png"))

def test_generator_uses_asset_provider_for_tags(mock_asset_provider, basic_config, tmp_path):
    gen = Generator(basic_config, output_dir=tmp_path)
    scene = gen.generate_scene(0)
    
    # Check if AssetProvider was used for tag textures
    # Tag texture resolution happens in _generate_layout_objects
    mock_asset_provider.resolve_path.assert_any_call("tags/tag36h11")
    assert scene.objects[0].properties["texture_base_path"] == str(Path("/mock/assets/tags/tag36h11"))
