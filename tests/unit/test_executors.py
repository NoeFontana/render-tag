from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from render_tag.core.config import GenConfig
from render_tag.core.schema.job import JobInfrastructure, JobPaths, JobSpec
from render_tag.orchestration.orchestrator import ExecutorFactory, LocalExecutor


def create_dummy_job_spec(tmp_path):
    return JobSpec(
        job_id="test-job",
        paths=JobPaths(
            output_dir=tmp_path / "output",
            logs_dir=tmp_path / "logs",
            assets_dir=tmp_path / "assets",
        ),
        infrastructure=JobInfrastructure(),
        global_seed=42,
        scene_config=GenConfig(),
        env_hash="abc",
        blender_version="4.2.0",
        assets_hash="123",
    )


def test_executor_factory_returns_correct_types():
    """Verify that ExecutorFactory returns the expected implementation types."""
    assert isinstance(ExecutorFactory.get_executor("local"), LocalExecutor)

    with pytest.raises(ValueError, match="Unknown executor type: invalid"):
        ExecutorFactory.get_executor("invalid")


@patch("render_tag.orchestration.orchestrator.UnifiedWorkerOrchestrator")
def test_local_executor_handoff_to_orchestrator(mock_orch, tmp_path):
    """Verify that LocalExecutor correctly initializes the orchestrator."""
    from render_tag.orchestration.orchestrator import LocalExecutor

    # Setup mock orchestrator context manager
    mock_instance = mock_orch.return_value
    mock_instance.__enter__.return_value = mock_instance

    executor = LocalExecutor()
    job_spec = create_dummy_job_spec(tmp_path)

    # Mock file existence for recipes
    recipe_path = job_spec.paths.output_dir / "recipes_shard_shard_1.json"

    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("builtins.open", MagicMock()),
        patch("json.load") as mock_json,
    ):
        # Make recipe path and fallback exist checks pass
        # The logic checks recipe_path first.
        # We need mock_exists to return True for recipe_path
        # But Path.exists is called on recipe_path object instance.
        # Patching pathlib.Path.exists affects all instances.
        mock_exists.return_value = True

        mock_json.return_value = [{"scene_id": 1}]

        executor.execute(
            job_spec=job_spec,
            shard_id="shard_1",
        )

    # Verify orchestrator was called with correct args
    assert mock_orch.called
    _, kwargs = mock_orch.call_args
    assert kwargs["num_workers"] == 1
    assert kwargs["ephemeral"] is True
    assert kwargs["seed"] == 42


@patch("subprocess.run")
def test_docker_executor_execution(mock_run, tmp_path):
    """Verify that DockerExecutor calls docker with correct volume mappings."""
    from render_tag.orchestration.orchestrator import DockerExecutor

    mock_run.return_value = MagicMock(returncode=0)
    docker = DockerExecutor(image="render-tag:latest")

    job_spec = create_dummy_job_spec(tmp_path)

    docker.execute(job_spec=job_spec, shard_id="shard_1")

    assert mock_run.called
    args, _ = mock_run.call_args
    cmd = args[0]

    assert cmd[0] == "docker"
    assert cmd[1] == "run"

    # Check volume mount for output dir
    # output_dir is tmp_path / "output". docker command uses .absolute()
    # verify that the mount string exists in cmd list
    mount_point = f"{job_spec.paths.output_dir.absolute()}:/output"
    assert mount_point in cmd

    assert "render-tag:latest" in cmd
    # Check if job-spec arg is passed
    assert "--job-spec" in cmd
    assert "/output/job_spec.json" in cmd
    assert "--shard-id" in cmd
    assert "shard_1" in cmd
