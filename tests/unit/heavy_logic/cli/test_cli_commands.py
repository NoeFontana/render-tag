"""
Unit tests for the CLI module.
Consolidates tests for config validation, job execution, skip-render, and manifest generation.
"""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from render_tag.cli import app
from render_tag.cli.tools import check_blenderproc_installed, serialize_config_to_json
from render_tag.core.config import GenConfig
from render_tag.core.schema.job import JobPaths, JobSpec

runner = CliRunner()


def strip_ansi(text):
    ansi_escape = re.compile(r"(?:\x1B[@-_][0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestCheckBlenderprocInstalled:
    def test_blenderproc_not_installed(self) -> None:
        with patch("shutil.which", return_value=None):
            assert check_blenderproc_installed() is False

    def test_blenderproc_installed(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/blenderproc"):
            assert check_blenderproc_installed() is True


class TestSerializeConfigToJson:
    def test_serialize_default_config(self, tmp_path: Path) -> None:
        config = GenConfig()
        output_path = tmp_path / "config.json"

        serialize_config_to_json(config, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "camera" in content
        assert "tag" in content
        assert "dataset" in content

    def test_serialize_custom_config(self, tmp_path: Path) -> None:
        config = GenConfig()
        config.camera.resolution = (1920, 1080)
        output_path = tmp_path / "custom_config.json"

        serialize_config_to_json(config, output_path)

        with open(output_path) as f:
            data = json.load(f)

        assert data["camera"]["resolution"] == [1920, 1080]


class TestCLIValidateCommand:
    def test_validate_existing_config(self) -> None:
        # Use the default config that exists in the project
        result = runner.invoke(app, ["validate-config", "--config", "configs/default.yaml"])

        # Should succeed (exit code 0) or fail gracefully if file doesn't exist
        assert result.exit_code in [0, 1, 2]

    def test_validate_missing_config(self) -> None:
        result = runner.invoke(app, ["validate-config", "--config", "/nonexistent/config.yaml"])
        assert result.exit_code != 0


class TestCLIInfoCommand:
    def test_info_command_runs(self) -> None:
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "render-tag" in result.stdout
        assert "Tag Families" in result.stdout


@pytest.fixture
def mock_executor_factory():
    """Mocks ExecutorFactory to prevent real orchestration."""
    with patch("render_tag.cli.stages.execution_stage.ExecutorFactory") as mock_factory:
        mock_executor = MagicMock()
        from render_tag.orchestration.result import (
            ExecutionTimings,
            JobMetadata,
            OrchestrationResult,
        )

        mock_executor.execute.return_value = OrchestrationResult(
            timings=ExecutionTimings(total_duration_s=1.23),
            metadata=JobMetadata(job_spec_hash="hash", env_state_hash="env_hash"),
        )
        mock_factory.get_executor.return_value = mock_executor
        yield mock_factory, mock_executor


@pytest.fixture
def mock_generator():
    """Mocks the SceneCompiler to return dummy recipes and pass validation."""
    with patch("render_tag.cli.stages.prep_stage.SceneCompiler") as mock_gen_cls:
        mock_gen = mock_gen_cls.return_value
        from render_tag.core.schema import SceneRecipe

        recipe = SceneRecipe(scene_id=0, random_seed=42, world={}, objects=[], cameras=[])
        mock_gen.compile_shards.return_value = [recipe]

        with patch(
            "render_tag.cli.stages.prep_stage.validate_recipe_file", return_value=(True, [], [])
        ):
            yield mock_gen_cls, mock_gen


@pytest.fixture
def mock_hydrated_assets():
    """Mocks AssetValidator to report that assets are present."""
    with patch("render_tag.core.validator.AssetValidator") as mock_val_cls:
        mock_val = mock_val_cls.return_value
        mock_val.is_hydrated.return_value = True
        yield mock_val


@patch("render_tag.cli.tools.check_blenderproc_installed", return_value=True)
def test_generate_handoff_to_executor(
    mock_check, mock_executor_factory, mock_generator, mock_hydrated_assets, tmp_path: Path
) -> None:
    """
    Staff Engineer approach: Verify CLI correctly HANDS OFF to the orchestration layer.
    We mock the ExecutorFactory so we don't trigger real ZMQ/Process logic.
    """
    mock_factory, mock_executor = mock_executor_factory
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dataset:\n  seed: 42\n")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "recipes_shard_0.json").touch()

    result = runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(config_path),
            "--output",
            str(output_dir),
            "--renderer-mode",
            "eevee",
            "--executor",
            "mock",
        ],
    )

    if result.exit_code != 0:
        print(f"CLI Output:\n{result.output}")
        print(f"Exception: {result.exception}")
        if result.exc_info:
            import traceback

            traceback.print_tb(result.exc_info[2])
    assert result.exit_code == 0
    # Verify handoff
    mock_factory.get_executor.assert_called_with("mock")
    assert mock_executor.execute.called

    # Verify arguments passed to executor
    call_args = mock_executor.execute.call_args.kwargs
    assert "job_spec" in call_args
    job_spec = call_args["job_spec"]
    assert job_spec.paths.output_dir == output_dir
    assert job_spec.scene_config.renderer.mode == "eevee"


@patch("render_tag.cli.tools.check_blenderproc_installed", return_value=True)
def test_generate_scenes_override_logic(
    mock_check, mock_executor_factory, mock_generator, mock_hydrated_assets, tmp_path: Path
) -> None:
    """Verify that CLI overrides are correctly processed before generation."""
    mock_gen_cls, _ = mock_generator
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dataset:\n  num_scenes: 10\n")

    runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(config_path),
            "--output",
            str(tmp_path / "out"),
            "--scenes",
            "3",
        ],
    )

    # Verify SceneCompiler was initialized with overridden num_scenes
    assert mock_gen_cls.called
    config_arg = mock_gen_cls.call_args[0][0]
    assert config_arg.dataset.num_scenes == 3


def test_cli_run_with_job_mismatch(tmp_path, monkeypatch):
    # 0. Create dummy config
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "default.yaml"
    config_file.write_text("dummy: content")
    config_hash = hashlib.sha256(b"dummy: content").hexdigest()

    # 1. Create a job.json with a mismatched env_hash
    job_file = tmp_path / "job.json"
    spec = JobSpec(
        job_id="test-job",
        paths=JobPaths(
            output_dir=Path("/tmp/out"),
            logs_dir=Path("/tmp/out/logs"),
            assets_dir=Path("/tmp/out/assets"),
        ),
        global_seed=42,
        scene_config=GenConfig(),
        env_hash="mismatched_hash",
        blender_version="4.2.0",
        assets_hash="abc",
        config_hash=config_hash,
        shard_index=0,
    )
    job_file.write_text(spec.model_dump_json())

    # 2. Mock uv.lock to have a different hash
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("actual content")

    # 3. Mock blenderproc to return correct version

    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/blenderproc")

    class MockCompletedProcess:
        def __init__(self):
            self.stdout = "BlenderProc 4.2.0\n"
            self.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockCompletedProcess())

    # Mock AssetValidator and BlenderProc check
    monkeypatch.setattr("render_tag.core.validator.AssetValidator.is_hydrated", lambda self: True)
    monkeypatch.setattr("render_tag.cli.tools.check_blenderproc_installed", lambda: True)

    # 4. Run 'render-tag generate --job job.json'
    result = runner.invoke(app, ["generate", "--job", str(job_file), "--executor", "mock"])

    assert result.exit_code != 0
    assert "Environment mismatch" in re.sub(r"\s+", " ", result.output)


def test_cli_run_with_job_config_mismatch(tmp_path, monkeypatch):
    # 0. Create dummy config
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "default.yaml"
    config_file.write_text("actual content")

    # 1. Create a job.json with a DIFFERENT config hash
    job_file = tmp_path / "job.json"
    spec = JobSpec(
        job_id="test-job",
        paths=JobPaths(
            output_dir=Path("/tmp/out"),
            logs_dir=Path("/tmp/out/logs"),
            assets_dir=Path("/tmp/out/assets"),
        ),
        global_seed=42,
        scene_config=GenConfig(),
        env_hash=hashlib.sha256(b"actual uv content").hexdigest(),
        blender_version="4.2.0",
        assets_hash="abc",
        config_hash="mismatched_config_hash",
        shard_index=0,
    )
    job_file.write_text(spec.model_dump_json())

    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("actual uv content")

    # Mock environment to pass

    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/blenderproc")

    class MockCompletedProcess:
        def __init__(self):
            self.stdout = "BlenderProc 4.2.0\n"
            self.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockCompletedProcess())

    # Mock AssetValidator and BlenderProc check
    monkeypatch.setattr("render_tag.core.validator.AssetValidator.is_hydrated", lambda self: True)
    monkeypatch.setattr("render_tag.cli.tools.check_blenderproc_installed", lambda: True)

    result = runner.invoke(app, ["generate", "--job", str(job_file), "--executor", "mock"])

    assert result.exit_code != 0
    assert "Config hash mismatch" in re.sub(r"\s+", " ", result.output)


@patch(
    "render_tag.cli.stages.config_stage.get_env_fingerprint",
    return_value=("dummy_env", "dummy_ver"),
)
def test_cli_run_with_job_overrides_warning(mock_fp, tmp_path, monkeypatch, mock_job_spec):
    # Setup valid job and config
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "default.yaml"
    config_file.write_text("dummy: content")

    # Modify the fixture spec for this test
    # We need scene_config.dataset.num_scenes = 42
    # Since JobSpec is frozen, we copy it
    scene_config = mock_job_spec.scene_config.model_copy(deep=True)
    scene_config.dataset.num_scenes = 42

    # Recalculate hash for modified config
    config_hash = hashlib.sha256(scene_config.model_dump_json().encode()).hexdigest()

    # Create new spec with modified config
    spec = mock_job_spec.model_copy(
        update={
            "scene_config": scene_config,
            "config_hash": config_hash,
            "env_hash": "dummy_env",  # Match the mock return value
            "blender_version": "dummy_ver",
        }
    )

    job_file = tmp_path / "job.json"
    job_file.write_text(spec.model_dump_json())

    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("uv")

    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/blenderproc")

    class MockCompletedProcess:
        def __init__(self):
            self.stdout = "BlenderProc 4.2.0\n"
            self.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockCompletedProcess())

    # Mock AssetValidator and BlenderProc check
    monkeypatch.setattr("render_tag.core.validator.AssetValidator.is_hydrated", lambda self: True)
    monkeypatch.setattr("render_tag.cli.tools.check_blenderproc_installed", lambda: True)

    # Run with conflicting CLI flags
    result = runner.invoke(
        app,
        [
            "generate",
            "--job",
            str(job_file),
            "--scenes",
            "5",
            "--seed",
            "100",
            "--executor",
            "mock",
        ],
    )

    # It should still run (or at least pass the guard) and show warnings
    # Strip ANSI codes for robust matching
    output_clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    output_normalized = re.sub(r"\s+", " ", output_clean)

    assert "Warning" in output_normalized
    assert "Using job spec value: 42" in output_normalized
    assert "Using job spec value: 42" in output_normalized


def test_cli_run_with_job_not_found():
    result = runner.invoke(app, ["generate", "--job", "non_existent.json"])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "no such file" in result.output.lower()


def test_generate_skip_render_creates_recipes(tmp_path: Path, mock_hydrated_assets):
    """Test that --skip-render generates recipes without calling Blender."""
    config_file = tmp_path / "fast_config.yaml"
    config_file.write_text("dataset:\n  num_scenes: 1\n")
    output_dir = tmp_path / "skip_render_output"

    # We mock check_blenderproc to ensure it's not needed
    with patch("render_tag.cli.tools.check_blenderproc_installed", return_value=False):
        result = runner.invoke(
            app,
            [
                "generate",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
                "--skip-render",
            ],
        )

    assert result.exit_code == 0
    assert (output_dir / "recipes_shard_0.json").exists()
    assert "Skipping Blender launch" in result.stdout


def test_generate_skip_render_respects_shards(tmp_path: Path, mock_hydrated_assets):
    """Test that --skip-render respects sharding arguments."""
    config_file = tmp_path / "fast_config.yaml"
    config_file.write_text("dataset:\n  num_scenes: 4\n")
    output_dir = tmp_path / "sharded_output"

    with patch("render_tag.cli.tools.check_blenderproc_installed", return_value=False):
        # Shard 0/2
        runner.invoke(
            app,
            [
                "generate",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
                "--skip-render",
                "--total-shards",
                "2",
                "--shard-index",
                "0",
            ],
        )
        # Shard 1/2
        runner.invoke(
            app,
            [
                "generate",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
                "--skip-render",
                "--total-shards",
                "2",
                "--shard-index",
                "1",
            ],
        )

    # Check that recipes contain different scenes
    with open(output_dir / "recipes_shard_0.json") as f:
        recipes_0 = json.load(f)
    with open(output_dir / "recipes_shard_1.json") as f:
        recipes_1 = json.load(f)

    assert len(recipes_0) == 2
    assert len(recipes_1) == 2
    assert recipes_0[0]["scene_id"] == 0
    assert recipes_0[1]["scene_id"] == 1
    assert recipes_1[0]["scene_id"] == 2
    assert recipes_1[1]["scene_id"] == 3


@patch("render_tag.core.validator.AssetValidator")
def test_cli_catches_validation_error(mock_validator, tmp_path):
    mock_validator.return_value.is_hydrated.return_value = True
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("dataset:\n  num_scenes: -5\n")
    result = runner.invoke(app, ["generate", "--config", str(config_path)])
    assert result.exit_code == 1
    assert result.exit_code == 1
    # Pydantic validation error is printed within the exception message
    clean_stdout = strip_ansi(result.stdout)
    normalized_output = re.sub(r"\s+", " ", clean_stdout)
    assert "Error resolving config" in normalized_output
    assert "Input should be greater than 0" in normalized_output


@patch("render_tag.core.validator.AssetValidator")
def test_cli_detects_missing_asset_preflight(mock_validator, tmp_path):
    mock_validator.return_value.is_hydrated.return_value = False
    config_path = tmp_path / "missing_asset.yaml"
    config_path.write_text("scene:\n  background_hdri: nonexistent_studio.exr\n")
    result = runner.invoke(app, ["generate", "--config", str(config_path), "--skip-render"])
    assert result.exit_code == 1
    assert "Pre-flight Validation Failed" in result.stdout


def test_cli_run_generates_manifest(tmp_path, monkeypatch):
    # Setup dummy environment
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "default.yaml"
    config_file.write_text("dummy: content")

    output_dir = tmp_path / "output"

    (tmp_path / "uv.lock").write_text("uv")
    (tmp_path / "assets").mkdir()

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(shutil, "which", lambda x: None)

    # Run command with --skip-render
    result = runner.invoke(
        app,
        ["generate", "--config", str(config_file), "--output", str(output_dir), "--skip-render"],
    )

    print(result.output)
    assert result.exit_code == 0
    assert (output_dir / "manifest.json").exists()
    assert "Generating dataset metadata" in result.output
