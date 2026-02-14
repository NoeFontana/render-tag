import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from render_tag.orchestration.orchestrator import ExecutorFactory, LocalExecutor


def test_executor_factory_returns_correct_types():
    """Verify that ExecutorFactory returns the expected implementation types."""
    assert isinstance(ExecutorFactory.get_executor("local"), LocalExecutor)

    with pytest.raises(ValueError, match="Unknown executor type: invalid"):
        ExecutorFactory.get_executor("invalid")


@patch("render_tag.orchestration.orchestrator.UnifiedWorkerOrchestrator")
def test_local_executor_handoff_to_orchestrator(mock_orch):
    """Verify that LocalExecutor correctly initializes the orchestrator."""
    from render_tag.orchestration.orchestrator import LocalExecutor

    # Setup mock orchestrator context manager
    mock_instance = mock_orch.return_value
    mock_instance.__enter__.return_value = mock_instance

    executor = LocalExecutor()
    recipe_path = Path("recipe.json")
    output_dir = Path("output")

    # We need a real-ish recipe file for json.load
    with patch("builtins.open", MagicMock()):
        with patch("json.load") as mock_json:
            mock_json.return_value = [{"scene_id": 1}]
            executor.execute(
                recipe_path=recipe_path,
                output_dir=output_dir,
                renderer_mode="cycles",
                shard_id="shard_1",
            )

    # Verify orchestrator was called with num_workers=1
    assert mock_orch.called
    _, kwargs = mock_orch.call_args
    assert kwargs["num_workers"] == 1
    assert kwargs["ephemeral"] is True


@patch("subprocess.run")
def test_docker_executor_execution(mock_run):
    """Verify that DockerExecutor calls docker with correct volume mappings."""
    from render_tag.orchestration.orchestrator import DockerExecutor

    mock_run.return_value = MagicMock(returncode=0)
    docker = DockerExecutor(image="render-tag:latest")

    recipe_path = Path("/abs/path/to/recipe.json")
    output_dir = Path("/abs/path/to/output")

    docker.execute(
        recipe_path=recipe_path, output_dir=output_dir, renderer_mode="cycles", shard_id="shard_1"
    )

    assert mock_run.called
    args, _ = mock_run.call_args
    cmd = args[0]

    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert f"{output_dir.absolute()}:/output" in cmd
    assert "render-tag:latest" in cmd
    # Use any() to check for the backend script path substring
    assert any("zmq_server.py" in part for part in cmd)
