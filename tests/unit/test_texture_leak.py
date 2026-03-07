from unittest.mock import MagicMock, patch
from render_tag.backend.scene import setup_floor_material

@patch("render_tag.backend.scene.bridge")
def test_setup_floor_material_texture_leak(mock_bridge):
    """
    Test that setup_floor_material currently leaks memory by loading 
    the same image multiple times.
    """
    mock_obj = MagicMock()
    texture_path = "/fake/path/texture.png"
    
    # Mock bpy.data.images
    mock_images = MagicMock()
    # Simulate pooling: first call returns None, second returns the loaded image
    mock_image = MagicMock()
    mock_images.get.side_effect = [None, mock_image]
    mock_images.load.return_value = mock_image
    mock_bridge.bpy.data.images = mock_images
    
    # Mock materials to avoid clear() and append() errors
    mock_obj.blender_obj.data.materials = []
    
    with patch("render_tag.backend.scene.Path") as mock_path:
        # Mock Path(texture_path).name and Path(texture_path).exists()
        mock_path_instance = MagicMock()
        mock_path_instance.name = "texture.png"
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance
        
        # ACT: Call twice with the same path
        setup_floor_material(mock_obj, texture_path=texture_path)
        setup_floor_material(mock_obj, texture_path=texture_path)
    
    # VERIFY: load() should be called only ONCE
    assert mock_images.load.call_count == 1, \
        f"Texture was loaded {mock_images.load.call_count} times, expected 1"
    # get() should be called twice (once per floor setup)
    assert mock_images.get.call_count == 2

def test_setup_floor_material_pooling():
    """
    Placeholder for the FIXED implementation verification.
    """
    pass
