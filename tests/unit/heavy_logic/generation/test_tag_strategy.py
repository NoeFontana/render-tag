from pathlib import Path
from unittest.mock import MagicMock

from render_tag.cli.pipeline import GenerationContext
from render_tag.core.config import GenConfig
from render_tag.core.schema.subject import TagSubjectConfig
from render_tag.generation.strategy.tags import TagStrategy


def test_tag_strategy_sample_pose():
    config = TagSubjectConfig(tag_families=["tag36h11"], size_meters=0.1, tags_per_scene=5)
    strategy = TagStrategy(config)

    # Mock context
    ctx = MagicMock(spec=GenerationContext)
    ctx.gen_config = GenConfig()
    ctx.gen_config.scenario.use_board = False
    ctx.output_dir = Path("output")

    # We expect sample_pose to return a list of 5 ObjectRecipes
    objects = strategy.sample_pose(seed=42, context=ctx)
    assert len(objects) == 5
    for obj in objects:
        assert obj.type == "TAG"
        assert obj.properties["tag_family"] == "tag36h11"
        assert obj.properties["tag_size"] == 0.1


def test_tag_strategy_prepare_assets():
    config = TagSubjectConfig(tag_families=["tag36h11"], size_meters=0.1, tags_per_scene=5)
    strategy = TagStrategy(config)

    ctx = MagicMock(spec=GenerationContext)
    # Asset preparation logic might involve ensuring tag textures exist in output/cache
    # For now we just check it doesn't crash
    strategy.prepare_assets(ctx)
