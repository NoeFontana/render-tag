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


def test_kalibr_corner_ratio():
    """Verify kalibr_corner_ratio changes corner square area and that
    different ratios produce different textures."""
    base = {
        "type": BoardType.APRILGRID,
        "rows": 2,
        "cols": 2,
        "marker_size": 0.1,
        "spacing_ratio": 0.3,
    }
    factory = TextureFactory(px_per_mm=10)

    img_default = factory.generate_board_texture(BoardConfig(**base))
    img_large = factory.generate_board_texture(BoardConfig(**base, kalibr_corner_ratio=0.5))

    # Larger corner ratio → more black pixels → lower mean
    assert np.mean(img_large) < np.mean(img_default)

    # Hash must differ when kalibr_corner_ratio differs
    assert factory._calculate_hash(BoardConfig(**base)) != factory._calculate_hash(
        BoardConfig(**base, kalibr_corner_ratio=0.5)
    )


def test_kalibr_corner_symmetry():
    """Verify corner squares are placed symmetrically around grid intersections."""
    # 1x1 board: intersections at x=0, x=square_px, y=0, y=square_px
    # px_per_mm=10 -> px_per_m=10000
    # square_size = 0.1 * (1 + 1.0) = 0.2m -> 2000px
    # marker_px = 0.1 * 10000 = 1000px
    # corner_ratio=0.2 -> corner_half = 1000 * 0.2 / 2 = 100px
    # Interior intersection at (2000, 2000) — outside 1x1 board? No:
    # rows+1=2, cols+1=2, so intersections at r=0,1 c=0,1
    # Interior intersection at (2000, 2000) is the bottom-right corner
    # Use a corner in the middle: rows=2, cols=2 -> interior at (2000, 2000)
    config = BoardConfig(
        type=BoardType.APRILGRID,
        rows=2,
        cols=2,
        marker_size=0.01,
        spacing_ratio=1.0,
        kalibr_corner_ratio=0.4,
    )
    # px_per_mm=10 -> square_px = 0.01*2 * 10000 = 200px
    # corner_half = 0.01*10000 * 0.4 / 2 = 20px
    # Interior intersection at (200, 200)
    # Expected square: rows [180, 220), cols [180, 220) -> 40x40 px
    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    # Extract the interior intersection region and verify it is all black
    # The square centered at pixel (200, 200) with half=20 spans [180:220, 180:220]
    region = img[180:220, 180:220]
    assert np.all(region == 0), "Interior corner square must be fully black"

    # Verify symmetry: equal black extent on each side of the intersection
    row_center = 200
    col_center = 200
    # Look 1 pixel inside the half-extent boundary on each side
    assert img[row_center - 19, col_center] == 0  # above center
    assert img[row_center + 19, col_center] == 0  # below center
    assert img[row_center, col_center - 19] == 0  # left of center
    assert img[row_center, col_center + 19] == 0  # right of center


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
