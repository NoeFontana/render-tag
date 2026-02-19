from unittest.mock import MagicMock, patch

from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler
from render_tag.generation.strategy.base import SubjectStrategy


def test_compiler_agnostic_loop():
    config = GenConfig()
    config.dataset.num_scenes = 2
    
    # Mock strategy
    mock_strategy = MagicMock(spec=SubjectStrategy)
    mock_strategy.sample_pose.return_value = [] # Return empty objects for simplicity
    
    with patch("render_tag.generation.compiler.get_subject_strategy", return_value=mock_strategy):
        compiler = SceneCompiler(config)
        
        # compile_shards should:
        # 1. Call get_subject_strategy (done in __init__)
        # 2. Call prepare_assets once (before the loop)
        # 3. Call sample_pose once per scene
        recipes = compiler.compile_shards(shard_index=0, total_shards=1)
        
        assert len(recipes) == 2
        assert mock_strategy.prepare_assets.called
        assert mock_strategy.sample_pose.call_count == 2
