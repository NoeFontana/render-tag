import numpy as np

from render_tag.core.schema.board import BoardConfig, BoardType
from render_tag.generation.texture_factory import TextureFactory


def test_texture_factory_aprilgrid():
    """Verify AprilGrid texture generation."""
    config = BoardConfig(
        type=BoardType.APRILGRID,
        rows=3,
        cols=4,
        marker_size=0.08,
        spacing_ratio=0.3,
        dictionary="tag36h11",
    )
    # 10px/mm = 10000px/m
    # Board size: cols*square_size, rows*square_size
    # square_size for AprilGrid = marker_size * (1 + spacing_ratio)
    # square_size = 0.08 * 1.3 = 0.104m
    # width = 4 * 0.104 = 0.416m -> 4160px
    # height = 3 * 0.104 = 0.312m -> 3120px

    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    assert img.shape == (3120, 4160)
    assert img.dtype == np.uint8
    # AprilGrid has tags in every cell + small black corner squares
    # (0.08 / 0.104)^2 = ~0.59 area is tag.
    # Tags are mostly black, so mean should be around 100-180
    assert 100 < np.mean(img) < 200


def test_texture_factory_charuco():
    """Verify ChArUco texture generation."""
    config = BoardConfig(
        type=BoardType.CHARUCO,
        rows=5,
        cols=5,
        square_size=0.05,
        marker_size=0.04,
        dictionary="DICT_4X4_50",
    )
    # width = 5 * 0.05 = 0.25m -> 2500px
    # height = 5 * 0.05 = 0.25m -> 2500px

    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    assert img.shape == (2500, 2500)
    # ChArUco has 50% black squares + tags in white squares
    # Mean should be significantly lower than AprilGrid
    assert 40 < np.mean(img) < 100


def test_texture_factory_caching(tmp_path):
    """Verify that textures are cached."""
    config = BoardConfig(
        type=BoardType.APRILGRID, rows=2, cols=2, marker_size=0.08, spacing_ratio=0.3
    )

    factory = TextureFactory(px_per_mm=1, cache_dir=tmp_path)
    img1 = factory.generate_board_texture(config)

    # Check if file exists in cache
    cache_files = list(tmp_path.glob("*.png"))
    assert len(cache_files) == 1

    # Second call should use cache
    img2 = factory.generate_board_texture(config)
    assert np.array_equal(img1, img2)


def test_texture_factory_id_increment():
    """Verify that tag IDs are incremented."""
    factory = TextureFactory(px_per_mm=1)

    # 2x1 AprilGrid (ID 0 and ID 1)
    config = BoardConfig(
        type=BoardType.APRILGRID, rows=1, cols=2, marker_size=0.1, spacing_ratio=0.5
    )
    img = factory.generate_board_texture(config)

    # Split image and compare tags
    # square_px = 0.1 * 1.5 * 1000 = 150
    # Wait, px_per_mm=1 -> px_per_m=1000
    # square_px = 150
    tag_0 = img[:, :150]
    tag_1 = img[:, 150:]

    assert not np.array_equal(tag_0, tag_1)


def test_texture_factory_hashing():
    """Verify that different configs produce different hashes."""
    factory = TextureFactory()
    config1 = BoardConfig(
        type=BoardType.APRILGRID, rows=2, cols=2, marker_size=0.1, spacing_ratio=0.1
    )
    config2 = BoardConfig(
        type=BoardType.APRILGRID, rows=2, cols=2, marker_size=0.1, spacing_ratio=0.2
    )

    assert factory._calculate_hash(config1) != factory._calculate_hash(config2)
