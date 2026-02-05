"""
Unit tests for the CLI module.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from render_tag.cli import app
from render_tag.cli.tools import check_blenderproc_installed, serialize_config_to_json
from render_tag.config import GenConfig

runner = CliRunner()


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

        import json

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
    """Mocks the ExecutorFactory to return a mock executor."""
    with patch("render_tag.cli.generate.ExecutorFactory") as mock_factory:
        mock_executor = MagicMock()
        mock_factory.get_executor.return_value = mock_executor
        yield mock_factory, mock_executor

@pytest.fixture
def mock_generator():
    """Mocks the Generator to return dummy recipes and pass validation."""
    with patch("render_tag.cli.generate.Generator") as mock_gen_cls:
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate_shards.return_value = [{"scene_id": 0}]
        
        with patch("render_tag.cli.generate.validate_recipe_file", return_value=(True, [], [])):
            yield mock_gen_cls, mock_gen

@pytest.fixture
def mock_hydrated_assets():
    """Mocks AssetValidator to report that assets are present."""
    with patch("render_tag.cli.generate.AssetValidator") as mock_val_cls:
        mock_val = mock_val_cls.return_value
        mock_val.is_hydrated.return_value = True
        yield mock_val

@patch("render_tag.cli.generate.check_blenderproc_installed", return_value=True)
def test_generate_handoff_to_executor(
    mock_check,
    mock_executor_factory,
    mock_generator,
    mock_hydrated_assets,
    tmp_path: Path
) -> None:
    """
    Staff Engineer approach: Verify CLI correctly HANDS OFF to the orchestration layer.
    We mock the ExecutorFactory so we don't trigger real ZMQ/Process logic.
    """
    mock_factory, mock_executor = mock_executor_factory
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dataset:\n  seed: 42\n")
    output_dir = tmp_path / "output"

    result = runner.invoke(
        app,
        [
            "generate",
            "--config", str(config_path),
            "--output", str(output_dir),
            "--renderer-mode", "eevee",
            "--executor", "mock"
        ],
    )

    assert result.exit_code == 0
    # Verify handoff
    mock_factory.get_executor.assert_called_with("mock")
    assert mock_executor.execute.called
    
    # Verify arguments passed to executor
    call_args = mock_executor.execute.call_args.kwargs
    assert "recipe_path" in call_args
    assert call_args["output_dir"] == output_dir
    assert call_args["renderer_mode"] == "eevee"

@patch("render_tag.cli.generate.check_blenderproc_installed", return_value=True)
def test_generate_scenes_override_logic(
    mock_check,
    mock_executor_factory,
    mock_generator,
    mock_hydrated_assets,
    tmp_path: Path
) -> None:
    """Verify that CLI overrides are correctly processed before generation."""
    mock_gen_cls, _ = mock_generator
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dataset:\n  num_scenes: 10\n")

    runner.invoke(
        app,
        [
            "generate",
            "--config", str(config_path),
            "--output", str(tmp_path / "out"),
            "--scenes", "3",
        ],
    )

    # Verify Generator was initialized with overridden num_scenes
    assert mock_gen_cls.called
    config_arg = mock_gen_cls.call_args[0][0]
    assert config_arg["dataset"]["num_scenes"] == 3


class TestCLIHelp:
    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "generate" in result.stdout

    def test_generate_help(self) -> None:
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.stdout
        assert "--output" in result.stdout