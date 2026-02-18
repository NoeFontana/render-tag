
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
        marker_size=0.04,
        square_size=0.05,
        dictionary="tag36h11"
    )
    strategy = BoardStrategy(config)
    
    ctx = MagicMock(spec=GenerationContext)
    ctx.gen_config = GenConfig()
    ctx.output_dir = Path("output")
    
    objects = strategy.sample_pose(seed=123, context=ctx)
    assert len(objects) == 1
    board = objects[0]
    assert board.type == "BOARD"
    # square_size * cols = 0.05 * 8 = 0.4
    # square_size * rows = 0.05 * 5 = 0.25
    assert board.scale == [0.4, 0.25, 1.0]
    assert len(board.keypoints_3d) > 0

def test_board_strategy_prepare_assets(tmp_path):
    config = BoardSubjectConfig(
        type="BOARD",
        rows=3,
        cols=3,
        marker_size=0.08,
        square_size=0.1,
        dictionary="tag36h11"
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
