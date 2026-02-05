import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from render_tag.orchestration.executors import RenderExecutor, ExecutorFactory, LocalExecutor, MockExecutor

def test_executor_factory_returns_correct_types():
    """Verify that the factory returns the expected executor implementations."""
    local = ExecutorFactory.get_executor("local")
    assert isinstance(local, LocalExecutor)
    
    mock = ExecutorFactory.get_executor("mock")
    assert isinstance(mock, MockExecutor)
    
    with pytest.raises(ValueError, match="Unknown executor type"):
        ExecutorFactory.get_executor("invalid")

def test_mock_executor_execution():
    """Verify that the mock executor 'executes' without side effects."""
    mock = ExecutorFactory.get_executor("mock")
    # Should not raise any errors
    mock.execute(
        recipe_path=Path("dummy_recipe.json"),
        output_dir=Path("/tmp/output"),
        renderer_mode="cycles",
        shard_id="0"
    )

@patch("subprocess.Popen")
def test_local_executor_execution(mock_popen):
    """Verify that LocalExecutor calls blenderproc with correct arguments."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("stdout", "stderr")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    local = LocalExecutor()
    
    recipe_path = Path("test_recipe.json")
    output_dir = Path("test_output")
    
    # Create dummy recipe file so script_path.exists() passes if checked
    # Actually script_path is executor.py, not recipe_path.
    # But some executors might check recipe_path.
    
    local.execute(
        recipe_path=recipe_path,
        output_dir=output_dir,
        renderer_mode="eevee",
        shard_id="42"
    )
    
    assert mock_popen.called
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    
    assert cmd[0] == "blenderproc"
    assert cmd[1] == "run"
    assert "executor.py" in cmd[2]
    assert "--recipe" in cmd
    assert str(recipe_path) in cmd

@patch("subprocess.run")
def test_docker_executor_execution(mock_run):
    """Verify that DockerExecutor calls docker with correct volume mappings."""
    from render_tag.orchestration.executors import DockerExecutor
    mock_run.return_value = MagicMock(returncode=0)
    docker = DockerExecutor(image="render-tag:latest")
    
    recipe_path = Path("/abs/path/to/recipe.json")
    output_dir = Path("/abs/path/to/output")
    
    docker.execute(
        recipe_path=recipe_path,
        output_dir=output_dir,
        renderer_mode="cycles",
        shard_id="shard_1"
    )
    
    assert mock_run.called
    args, _ = mock_run.call_args
    cmd = args[0]
    
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    # Check volume mapping for output
    assert "-v" in cmd
    # Ensure the output directory is mapped
    assert f"{output_dir.absolute()}:/output" in cmd
    # Check image name
    assert "render-tag:latest" in cmd
    # Check that it runs the backend script inside container
    assert "--recipe" in cmd
    assert "--output" in cmd
    assert "/output" in cmd
