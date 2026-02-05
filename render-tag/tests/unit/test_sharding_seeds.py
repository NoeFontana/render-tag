import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from render_tag.orchestration.sharding import run_local_parallel
from render_tag.config import GenConfig

def test_run_local_parallel_flow(tmp_path):
    """
    Test the high-level flow of run_local_parallel:
    - Load config
    - Generate recipes
    - Batching
    - Threaded execution
    """
    dummy_yaml = tmp_path / "dummy.yaml"
    dummy_yaml.write_text("dataset: {seed: 42}")
    
    with patch("render_tag.orchestration.sharding.load_config") as mock_load:
        with patch("render_tag.generator.Generator") as mock_gen_cls:
            with patch("render_tag.orchestration.executors.ExecutorFactory") as mock_exec_factory:
                with patch("threading.Thread") as mock_thread:
                    # Setup config mock
                    config = GenConfig()
                    mock_load.return_value = config
                    
                    # Setup generator mock
                    mock_gen = mock_gen_cls.return_value
                    mock_gen.generate_all.return_value = [{"scene_id": i} for i in range(5)]
                    mock_gen.save_recipe_json.return_value = Path("dummy_recipe.json")
                    
                    # Setup executor mock
                    mock_executor = MagicMock()
                    mock_exec_factory.get_executor.return_value = mock_executor
                    
                    # Run it with 2 workers and batch size 2 (should create 3 batches: 2, 2, 1)
                    run_local_parallel(
                        config_path=dummy_yaml,
                        output_dir=tmp_path / "out",
                        num_scenes=5,
                        workers=2,
                        renderer_mode="cycles",
                        verbose=False,
                        batch_size=2
                    )
                    
                    # Check calls
                    assert mock_gen.generate_all.called
                    # 5 scenes, batch size 2 => 3 batches
                    assert mock_gen.save_recipe_json.call_count == 3
                    # 2 worker threads should be started
                    assert mock_thread.call_count == 2
