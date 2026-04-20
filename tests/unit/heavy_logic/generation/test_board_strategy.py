from pathlib import Path
from unittest.mock import MagicMock

from render_tag.cli.pipeline import GenerationContext
from render_tag.core.config import GenConfig
from render_tag.core.schema.subject import BoardSubjectConfig
from render_tag.generation.strategy.board import BoardStrategy


def test_board_strategy_sample_pose():
    config = BoardSubjectConfig(
        type="BOARD",
        rows=5,
        cols=8,
        marker_size_mm=40.0,
        square_size_mm=50.0,
        dictionary="tag36h11",
    )
    strategy = BoardStrategy(config)

    ctx = MagicMock(spec=GenerationContext)
    ctx.gen_config = GenConfig()
    ctx.output_dir = Path("output")

    objects = strategy.sample_pose(seed=123, context=ctx)
    assert len(objects) == 1
    board = objects[0]
    assert board.type == "BOARD"
    # scale = [width_m/2, height_m/2, 1.0] to match the 2x2 Blender plane convention
    # width_m = 0.05 * 8 = 0.4  ->  scale_x = 0.2
    # height_m = 0.05 * 5 = 0.25 ->  scale_y = 0.125
    assert board.scale == [0.2, 0.125, 1.0]
    assert len(board.keypoints_3d) > 0


def test_board_strategy_keypoints_winding_order():
    """Verify that every tag's four keypoints follow the TL-CW contract.

    In Blender local space (Y-up) the four corners must be:
        index 0: Top-Left     (min X, max Y)
        index 1: Top-Right    (max X, max Y)
        index 2: Bottom-Right (max X, min Y)
        index 3: Bottom-Left  (min X, min Y)

    When projected into image space (Y-down) this produces a strictly Clockwise
    winding order (positive Shoelace signed area).
    """
    from unittest.mock import MagicMock

    from render_tag.cli.pipeline import GenerationContext
    from render_tag.core.config import GenConfig
    from render_tag.core.geometry.projection_math import validate_winding_order

    config = BoardSubjectConfig(
        type="BOARD",
        rows=3,
        cols=4,
        marker_size_mm=40.0,
        square_size_mm=50.0,
        dictionary="tag36h11",
    )
    strategy = BoardStrategy(config)

    ctx = MagicMock(spec=GenerationContext)
    ctx.gen_config = GenConfig()
    ctx.output_dir = None

    objects = strategy.sample_pose(seed=0, context=ctx)
    kps = objects[0].keypoints_3d
    assert kps is not None
    assert len(kps) % 4 == 0, "keypoints_3d must contain 4 corners per tag"

    for i in range(0, len(kps), 4):
        tl, tr, br, bl = kps[i], kps[i + 1], kps[i + 2], kps[i + 3]

        # Blender Y-up assertions: TL has max Y, BL/BR have min Y
        assert tl[1] > br[1], f"Tag {i // 4}: TL.y must be > BR.y (Y-up)"
        assert tr[1] > bl[1], f"Tag {i // 4}: TR.y must be > BL.y (Y-up)"
        assert tl[0] < tr[0], f"Tag {i // 4}: TL.x must be < TR.x"
        assert bl[0] < br[0], f"Tag {i // 4}: BL.x must be < BR.x"

        # In image-space (Y-down), the corners map to TL→TR→BR→BL (CW).
        # Simulate Y-down by negating Y before winding check.
        img_corners = [(tl[0], -tl[1]), (tr[0], -tr[1]), (br[0], -br[1]), (bl[0], -bl[1])]
        assert validate_winding_order(img_corners), (
            f"Tag {i // 4}: corners do not form a CW polygon in image space"
        )


def test_board_strategy_prepare_assets(tmp_path):
    config = BoardSubjectConfig(
        type="BOARD",
        rows=3,
        cols=3,
        marker_size_mm=80.0,
        square_size_mm=100.0,
        dictionary="tag36h11",
    )
    strategy = BoardStrategy(config)

    ctx = MagicMock(spec=GenerationContext)
    ctx.output_dir = tmp_path

    # This should generate the texture in tmp_path/cache/boards/
    strategy.prepare_assets(ctx)

    cache_dir = tmp_path / "cache" / "boards"
    assert cache_dir.exists()
    textures = list(cache_dir.glob("*.png"))
    assert len(textures) == 1
