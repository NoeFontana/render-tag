from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from render_tag.orchestration.sharding import run_local_parallel
from render_tag.config import GenConfig

def test_run_local_parallel_passes_seeds():
    # Mock subprocess.run
    with patch("subprocess.run") as mock_run:
        # Mock load_config
        with patch("render_tag.orchestration.sharding.load_config", create=True) as mock_load:
            # Mock config
            config = GenConfig()
            config.dataset.seeds.global_seed = 12345
            mock_load.return_value = config
            
            # Mock ProcessPoolExecutor to avoid pickling issues
            with patch("render_tag.orchestration.sharding.concurrent.futures.ProcessPoolExecutor") as mock_executor_cls:
                with patch("render_tag.orchestration.sharding.concurrent.futures.as_completed") as mock_as_completed:
                    mock_executor = mock_executor_cls.return_value
                    mock_executor.__enter__.return_value = mock_executor
                    
                    # Mock future
                    mock_future = MagicMock()
                    mock_future.result.return_value = None
                    mock_executor.submit.return_value = mock_future
                    
                    # as_completed yields futures immediately
                    mock_as_completed.return_value = [mock_future] * 2

                    # Verify submit calls
                    run_local_parallel(
                    config_path=Path("dummy.yaml"),
                    output_dir=Path("out"),
                    num_scenes=10,
                    workers=2,
                    renderer_mode="cycles",
                    verbose=False
                )
                
                # submit is called 2 times
                assert mock_executor.submit.call_count == 2
                
                # Check args passed to submit
                # submit(subprocess.run, cmd, check=True)
                args0 = mock_executor.submit.call_args_list[0][0][1] # cmd is second arg
                args1 = mock_executor.submit.call_args_list[1][0][1]
                
                # Expecting something like ... --seed <val> ...
                assert "--seed" in args0
                assert "--seed" in args1
                
                # Extract seeds
                idx0 = args0.index("--seed") + 1
                idx1 = args1.index("--seed") + 1
                seed0 = int(args0[idx0])
                seed1 = int(args1[idx1])
                
                assert seed0 != seed1
