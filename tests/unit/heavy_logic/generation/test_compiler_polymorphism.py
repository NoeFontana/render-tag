from render_tag.core.config import GenConfig
from render_tag.core.schema.subject import BoardSubjectConfig, TagSubjectConfig
from render_tag.generation.compiler import SceneCompiler


def test_compile_tag_subject():
    config = GenConfig()
    config.dataset.num_scenes = 1
    config.scenario.subject.root = TagSubjectConfig(
        tag_families=["tag36h11"], size_mm=100.0, tags_per_scene=5
    )

    compiler = SceneCompiler(config)
    recipes = compiler.compile_shards(shard_index=0, total_shards=1)
    recipe = recipes[0]

    # In Phase 2, we expect a unified ObjectRecipe for tags if possible,
    # or at least that the compiler doesn't crash.
    # The goal is that objects in recipe have keypoints.
    for obj in recipe.objects:
        assert obj.type in ["TAG", "BOARD"]
        # Generic keypoints should be present (4 for a tag)
        if obj.type == "TAG":
            assert len(obj.keypoints_3d) == 4


def test_compile_board_subject():
    config = GenConfig()
    config.dataset.num_scenes = 1
    config.scenario.subject.root = BoardSubjectConfig(
        type="BOARD",
        rows=3,
        cols=4,
        marker_size_mm=50.0,
        square_size_mm=60.0,
        dictionary="tag36h11",
    )

    compiler = SceneCompiler(config)
    recipes = compiler.compile_shards(shard_index=0, total_shards=1)
    recipe = recipes[0]

    # Should have exactly one BOARD object
    board_objs = [obj for obj in recipe.objects if obj.type == "BOARD"]
    assert len(board_objs) == 1
    board = board_objs[0]

    # Board should have many keypoints (tags + corners/saddle points)
    kps = board.keypoints_3d
    assert len(kps) > 0
