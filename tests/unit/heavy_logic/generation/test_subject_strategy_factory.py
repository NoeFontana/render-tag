import pytest

from render_tag.core.schema.subject import BoardSubjectConfig, TagSubjectConfig
from render_tag.generation.strategy.board import BoardStrategy
from render_tag.generation.strategy.factory import get_subject_strategy
from render_tag.generation.strategy.tags import TagStrategy


def test_get_subject_strategy_tags():
    config = TagSubjectConfig(tag_families=["tag36h11"], size_meters=0.1, tags_per_scene=10)
    strategy = get_subject_strategy(config)
    assert isinstance(strategy, TagStrategy)


def test_get_subject_strategy_board():
    config = BoardSubjectConfig(
        type="BOARD", rows=5, cols=8, marker_size=0.04, square_size=0.05, dictionary="tag36h11"
    )
    strategy = get_subject_strategy(config)
    assert isinstance(strategy, BoardStrategy)


def test_get_subject_strategy_invalid():
    with pytest.raises(ValueError, match="Unknown subject type"):
        get_subject_strategy(None)
