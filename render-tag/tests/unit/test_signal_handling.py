import signal
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from render_tag.orchestration.sharding import run_local_parallel

def test_run_local_parallel_installs_signal_handlers():
    """
    Test that run_local_parallel installs signal handlers for SIGINT and SIGTERM.
    """
    with patch("signal.signal") as mock_signal:
        with patch("subprocess.Popen") as mock_popen:
            with patch("render_tag.orchestration.sharding.load_config") as mock_load:
                # Setup mocks
                mock_load.return_value = MagicMock()
                mock_process = mock_popen.return_value
                mock_process.wait.return_value = 0
                mock_process.poll.return_value = 0
                
                try:
                    run_local_parallel(
                        config_path=Path("configs/default.yaml"),
                        output_dir=Path("output"),
                        num_scenes=10,
                        workers=2,
                        renderer_mode="cycles",
                        verbose=False
                    )
                except Exception:
                    pass
            
                # Check if signal.signal was called for SIGINT and SIGTERM
                sigint_called = any(call[0][0] == signal.SIGINT for call in mock_signal.call_args_list)
                sigterm_called = any(call[0][0] == signal.SIGTERM for call in mock_signal.call_args_list)
                
                assert sigint_called, "SIGINT handler not installed"
                assert sigterm_called, "SIGTERM handler not installed"

def test_signal_handler_terminates_processes():
    """
    Test that the _signal_handler function calls cleanup_render_processes.
    """
    from render_tag.orchestration.sharding import _signal_handler
    
    with patch("render_tag.orchestration.executors.cleanup_render_processes") as mock_cleanup:
        with patch("sys.exit") as mock_exit:
            _signal_handler(signal.SIGINT, None)
            
    assert mock_cleanup.called
    assert mock_exit.called

def test_run_local_parallel_reports_failure():
    """
    Test that run_local_parallel raises an error if a worker fails.
    """
    with patch("subprocess.Popen") as mock_popen:
        with patch("render_tag.orchestration.sharding.load_config") as mock_load:
            from typer import Exit
            
            # Setup mocks
            mock_load.return_value = MagicMock()
            mock_process = MagicMock()
            mock_process.wait.return_value = 1 # Failure
            mock_process.poll.return_value = 1
            mock_process.pid = 1234
            mock_popen.return_value = mock_process
            
            with pytest.raises(Exit):
                run_local_parallel(
                    config_path=Path("configs/default.yaml"),
                    output_dir=Path("output"),
                    num_scenes=10,
                    workers=1,
                    renderer_mode="cycles",
                    verbose=False
                )

def test_get_completed_scene_ids(tmp_path):
    """
    Test that get_completed_scene_ids identifies completed scenes based on sidecars.
    """
    from render_tag.orchestration.sharding import get_completed_scene_ids
    
    # Create a mock output directory
    output_dir = tmp_path / "output"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True)
    
    # Create some "completed" sidecars
    (images_dir / "scene_0001_meta.json").write_text("{}")
    (images_dir / "scene_0005_meta.json").write_text("{}")
    (images_dir / "other_file.txt").write_text("not a sidecar")
    
    completed = get_completed_scene_ids(output_dir)
    
    assert 1 in completed
    assert 5 in completed
    assert len(completed) == 2
