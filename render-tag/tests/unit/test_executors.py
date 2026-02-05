import pytest
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
