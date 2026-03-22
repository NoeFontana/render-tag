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

    # DICT_4X4_50 grid_size=6; marker_px_f=400 → snapped up to ceil(400/6)*6=402
    # effective_px_per_m = 402/0.04 = 10050
    # square_px_raw = 0.05*10050 = 502.5 → even-snapped to 502
    # Recomputed effective_px_per_m = 502/0.05 = 10040
    # width_px = height_px = 5 * 502 = 2510
    assert img.shape == (2510, 2510)
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

    # Split image at the cell boundary.
    # px_per_mm=1 → px_per_m=1000; marker_px=ceil(100/8)*8=104
    # effective_px_per_m=104/0.1=1040; square_size=0.15
    # square_px_raw=156 → even-snapped to 156
    tag_0 = img[:, :156]
    tag_1 = img[:, 156:]

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
    # tag36h11 grid_size=8; marker_px_f = 0.01*10000 = 100
    # marker_px = ceil(100/8)*8 = 13*8 = 104
    # effective_px_per_m = 104/0.01 = 10400
    # square_size = 0.01*(1+1.0) = 0.02m -> square_px_f = 0.02*10400 = 208px
    # corner_ratio=0.4 -> corner_px = max(2, int(104*0.4)&~1) = max(2,40) = 40
    # corner_half = 20px
    # rows=2, cols=2 -> interior intersection at r=1,c=1: (208, 208)
    # Corner square: rows [188:228), cols [188:228) -> 40x40 px
    config = BoardConfig(
        type=BoardType.APRILGRID,
        rows=2,
        cols=2,
        marker_size=0.01,
        spacing_ratio=1.0,
        kalibr_corner_ratio=0.4,
    )
    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    # Extract the interior intersection region and verify it is all black
    region = img[188:228, 188:228]
    assert np.all(region == 0), "Interior corner square must be fully black"

    # Verify symmetry: equal black extent on each side of the intersection
    row_center = 208
    col_center = 208
    # Look 1 pixel inside the half-extent boundary on each side
    assert img[row_center - 19, col_center] == 0  # above center
    assert img[row_center + 19, col_center] == 0  # below center
    assert img[row_center, col_center - 19] == 0  # left of center
    assert img[row_center, col_center + 19] == 0  # right of center


def test_kalibr_corner_uniform_size():
    """Verify all interior corner squares have identical pixel dimensions.

    Uses a config where the old float corner_half approach produced a half-integer
    value (corner_half = 2.5), which caused half-to-even rounding to alternate
    between 6-pixel and 4-pixel wide squares at successive grid intersections.
    """
    config = BoardConfig(
        type=BoardType.APRILGRID,
        rows=3,
        cols=4,
        marker_size=0.005,
        spacing_ratio=0.1,
        kalibr_corner_ratio=0.1,
    )
    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    gm = factory.compute_grid_metrics(config)

    widths: list[int] = []
    for r in range(1, config.rows):
        for c in range(1, config.cols):
            cy = r * gm.square_px
            cx = c * gm.square_px
            # Horizontal run: count consecutive black pixels centred on cx
            row = img[cy, :]
            # find extent of the black run that contains cx
            left = cx
            while left > 0 and row[left - 1] == 0:
                left -= 1
            right = cx
            while right < img.shape[1] - 1 and row[right + 1] == 0:
                right += 1
            widths.append(right - left + 1)

    assert len(widths) > 0
    assert all(w == widths[0] for w in widths), (
        f"Corner squares have inconsistent pixel widths: {widths}"
    )


def test_bit_grid_alignment():
    """Verify marker_px is snapped to a strict multiple of the tag grid size.

    If marker_px is not divisible by grid_size, generate_tag_image snaps it DOWN
    internally, producing a tag smaller than the cell and leaving an asymmetric
    white gap. The factory must snap UP so the requested size == actual size.
    """
    # DICT_4X4_50 has grid_size=6; at px_per_mm=10 and marker_size=0.04m:
    #   marker_px_f = 400, which is NOT a multiple of 6 (400/6 = 66.67)
    #   snapped up: ceil(400/6)*6 = 402
    config = BoardConfig(
        type=BoardType.CHARUCO,
        rows=3,
        cols=3,
        marker_size=0.04,
        square_size=0.05,
        dictionary="DICT_4X4_50",
    )
    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    gm = factory.compute_grid_metrics(config)

    from render_tag.core.constants import TAG_GRID_SIZES

    grid_size = TAG_GRID_SIZES.get("DICT_4X4_50", 8)
    assert gm.marker_px % grid_size == 0, (
        f"marker_px={gm.marker_px} is not a multiple of grid_size={grid_size}"
    )
    expected_width = config.cols * gm.square_px
    assert img.shape[1] == expected_width


def test_quiet_zone_pads_canvas():
    """Verify quiet_zone_m inflates the canvas and leaves a white border."""
    config_no_qz = BoardConfig(
        type=BoardType.APRILGRID,
        rows=2,
        cols=2,
        marker_size=0.08,
        spacing_ratio=0.3,
    )
    config_with_qz = BoardConfig(
        type=BoardType.APRILGRID,
        rows=2,
        cols=2,
        marker_size=0.08,
        spacing_ratio=0.3,
        quiet_zone_m=0.01,
    )
    # px_per_mm=10 -> px_per_m=10000; quiet_zone_px = round(0.01 * 10000) = 100
    factory = TextureFactory(px_per_mm=10)

    img_no_qz = factory.generate_board_texture(config_no_qz)
    img_with_qz = factory.generate_board_texture(config_with_qz)

    qz_px = 100
    # Canvas must be 2*qz_px larger in each dimension
    assert img_with_qz.shape[0] == img_no_qz.shape[0] + 2 * qz_px
    assert img_with_qz.shape[1] == img_no_qz.shape[1] + 2 * qz_px

    # Top and left quiet zone strips must be all white
    assert np.all(img_with_qz[:qz_px, :] == 255), "Top border must be white"
    assert np.all(img_with_qz[:, :qz_px] == 255), "Left border must be white"
    assert np.all(img_with_qz[-qz_px:, :] == 255), "Bottom border must be white"
    assert np.all(img_with_qz[:, -qz_px:] == 255), "Right border must be white"


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
