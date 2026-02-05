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

@patch("subprocess.run")
def test_local_executor_execution(mock_run):
    """Verify that LocalExecutor calls blenderproc with correct arguments."""
    mock_run.return_value = MagicMock(returncode=0)
    local = LocalExecutor()
    
    recipe_path = Path("test_recipe.json")
    output_dir = Path("test_output")
    
    local.execute(
        recipe_path=recipe_path,
        output_dir=output_dir,
        renderer_mode="eevee",
        shard_id="42"
    )
    
    assert mock_run.called
    args, kwargs = mock_run.call_args
    cmd = args[0]
    
    assert cmd[0] == "blenderproc"
    assert cmd[1] == "run"
    assert "executor.py" in cmd[2]
    assert "--recipe" in cmd
    assert str(recipe_path) in cmd
    assert "--output" in cmd
    assert str(output_dir) in cmd
    assert "--renderer-mode" in cmd
    assert "eevee" in cmd
    assert "--shard-id" in cmd
    assert "42" in cmd
