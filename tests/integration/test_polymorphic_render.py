import pytest
import numpy as np
from pathlib import Path
from render_tag.core.config import GenConfig
from render_tag.core.schema.subject import TagSubjectConfig, BoardSubjectConfig
from render_tag.generation.compiler import SceneCompiler
from render_tag.backend.engine import RenderFacade, execute_recipe
from render_tag.cli.pipeline import GenerationContext

@pytest.mark.integration
def test_polymorphic_render_tag(tmp_path):
    config = GenConfig()
    config.dataset.num_scenes = 1
    config.dataset.output_dir = tmp_path
    config.scenario.subject.root = TagSubjectConfig(
        tag_families=["tag36h11"],
        size_meters=0.1,
        tags_per_scene=2
    )
    
    compiler = SceneCompiler(config, output_dir=tmp_path)
    recipes = compiler.compile_shards(shard_index=0, total_shards=1)
    recipe = recipes[0]
    
    # We mock the context for execute_recipe
    from unittest.mock import MagicMock
    ctx = MagicMock(spec=GenerationContext)
    ctx.output_dir = tmp_path
    ctx.skip_visibility = False
    ctx.global_seed = 42
    ctx.logger = None
    ctx.renderer_mode = "cycles"
    ctx.coco_writer = MagicMock()
    ctx.csv_writer = MagicMock()
    ctx.sidecar_writer = MagicMock()
    
    # This might require Blender to be installed/available in the environment
    # If not, we might need to mock parts of the backend bridge.
    # But since it's an integration test, we try to run it.
    try:
        execute_recipe(recipe, ctx)
    except Exception as e:
        pytest.fail(f"Backend execution failed for TAG subject: {e}")

@pytest.mark.integration
def test_polymorphic_render_board(tmp_path):
    config = GenConfig()
    config.dataset.num_scenes = 1
    config.dataset.output_dir = tmp_path
    config.scenario.subject.root = BoardSubjectConfig(
        type="BOARD",
        rows=3,
        cols=3,
        marker_size=0.05,
        square_size=0.06,
        dictionary="tag36h11"
    )
    
    compiler = SceneCompiler(config, output_dir=tmp_path)
    recipes = compiler.compile_shards(shard_index=0, total_shards=1)
    recipe = recipes[0]
    
    from unittest.mock import MagicMock
    ctx = MagicMock(spec=GenerationContext)
    ctx.output_dir = tmp_path
    ctx.skip_visibility = False
    ctx.global_seed = 42
    ctx.logger = None
    ctx.renderer_mode = "cycles"
    ctx.coco_writer = MagicMock()
    ctx.csv_writer = MagicMock()
    ctx.sidecar_writer = MagicMock()
    
    try:
        execute_recipe(recipe, ctx)
    except Exception as e:
        pytest.fail(f"Backend execution failed for BOARD subject: {e}")
