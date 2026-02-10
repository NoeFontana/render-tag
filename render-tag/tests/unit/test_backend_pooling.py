from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock bpy/bproc for host-side tests
with (
    patch("render_tag.backend.assets.bpy", create=True) as mock_bpy,
    patch("render_tag.backend.assets.bproc", create=True) as mock_bproc,
):
    from render_tag.backend.assets import AssetPool, create_tag_plane


def test_asset_pool_retrieval():
    """Verify that AssetPool reuses objects."""
    mock_bproc = MagicMock()

    obj1 = MagicMock()
    obj1.name = "Obj1"
    obj2 = MagicMock()
    obj2.name = "Obj2"

    # Mock create_primitive to return unique objects
    mock_bproc.object.create_primitive.side_effect = [obj1, obj2]

    with patch("render_tag.backend.assets.bproc", mock_bproc):
        pool = AssetPool()

        # 1. First retrieval (empty pool)
        o1 = pool.get_tag()
        assert o1.name == "Obj1"
        assert mock_bproc.object.create_primitive.call_count == 1

        # 2. Release and second retrieval (reuse)
        pool.release_all()
        o1_again = pool.get_tag()
        assert o1_again is o1
        assert o1_again.name == "Obj1"
        assert mock_bproc.object.create_primitive.call_count == 1

        # 3. Third retrieval (new object needed)
        o2 = pool.get_tag()
        assert o2 is obj2
        assert o2.name == "Obj2"
        assert mock_bproc.object.create_primitive.call_count == 2


def test_create_tag_plane_uses_global_pool():
    """Verify that create_tag_plane integrates with the pool."""
    mock_pool = MagicMock()
    mock_tag = MagicMock()
    mock_pool.get_tag.return_value = mock_tag

    with (
        patch("render_tag.backend.assets.global_pool", mock_pool),
        patch("render_tag.backend.assets.apply_tag_texture"),
    ):
        # Should not call create_primitive directly
        tag = create_tag_plane(0.1, Path("tex.png"), "tag36h11")
        assert mock_pool.get_tag.called
        assert tag == mock_tag
