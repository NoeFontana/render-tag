from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from render_tag.orchestration.executors import (
    ExecutorFactory,
    LocalExecutor,
    MockExecutor,
)


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

def test_local_executor_handoff_to_orchestrator(tmp_path):
    """
    Staff Engineer approach: Verify LocalExecutor correctly configures the Unified Orchestrator.
    We mock the orchestrator to avoid starting real processes/ZMQ.
    """
    local = LocalExecutor()
    
    recipe_path = tmp_path / "test_recipe.json"
    # Create a dummy recipe list
    recipe_path.write_text('[{"scene_id": 0}]')
    output_dir = tmp_path / "test_output"
    
    with patch("render_tag.orchestration.executors.UnifiedWorkerOrchestrator") as mock_orch_cls:
        mock_orch = mock_orch_cls.return_value.__enter__.return_value
        mock_orch.execute_recipe.return_value = MagicMock(status="SUCCESS")
        
        local.execute(
            recipe_path=recipe_path,
            output_dir=output_dir,
            renderer_mode="eevee",
            shard_id="shard_42"
        )
        
        # Verify Orchestrator configuration
        mock_orch_cls.assert_called_once()
        _args, kwargs = mock_orch_cls.call_args
        assert kwargs["num_workers"] == 1
        assert kwargs["ephemeral"] is True
        
        # Verify execution call
        mock_orch.execute_recipe.assert_called_once()
        exec_args = mock_orch.execute_recipe.call_args[0]
        assert exec_args[0] == {"scene_id": 0}
        assert exec_args[1] == output_dir

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
    assert f"{output_dir.absolute()}:/output" in cmd
    assert "render-tag:latest" in cmd
    # Use any() to check for the backend script path substring
    assert any("executor.py" in part for part in cmd)