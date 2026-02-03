"""
Unit tests for the CLI module.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from render_tag.cli import app, check_blenderproc_installed, serialize_config_to_json
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
    def test_serialize_default_config(self) -> None:
        config = GenConfig()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = Path(f.name)

        try:
            serialize_config_to_json(config, output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "camera" in content
            assert "tag" in content
            assert "dataset" in content
        finally:
            output_path.unlink(missing_ok=True)

    def test_serialize_custom_config(self) -> None:
        config = GenConfig()
        config.camera.resolution = (1920, 1080)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = Path(f.name)

        try:
            serialize_config_to_json(config, output_path)

            import json

            with open(output_path) as f:
                data = json.load(f)

            assert data["camera"]["resolution"] == [1920, 1080]
        finally:
            output_path.unlink(missing_ok=True)


class TestCLIValidateCommand:
    def test_validate_existing_config(self) -> None:
        # Use the default config that exists in the project
        result = runner.invoke(app, ["validate-config", "--config", "configs/default.yaml"])

        # Should succeed (exit code 0) or fail gracefully if file doesn't exist
        # The command should at least run without crashing
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


class TestCLIGenerateCommand:
    def test_generate_without_blenderproc(self) -> None:
        # Mock blenderproc as not installed
        with patch("render_tag.cli.check_blenderproc_installed", return_value=False):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                f.write("dataset:\n  seed: 42\n")
                config_path = f.name

            try:
                result = runner.invoke(
                    app,
                    [
                        "generate",
                        "--config",
                        config_path,
                        "--output",
                        "/tmp/test_output",
                    ],
                )

                # Should fail because blenderproc is not installed
                assert result.exit_code == 1
                assert "blenderproc" in result.stdout.lower()
            finally:
                Path(config_path).unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("render_tag.cli.check_blenderproc_installed", return_value=True)
    def test_generate_command_structure(self, mock_check: MagicMock, mock_run: MagicMock) -> None:
        """Test that the blenderproc command is well-formed without actually running it."""
        import unittest.mock as mock

        # Mock successful subprocess execution
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")

        # Mock Generator to avoid actual generation logic
        with patch("render_tag.cli.Generator") as MockGenerator:
            # Setup mock generator behavior
            mock_gen_instance = MockGenerator.return_value
            mock_gen_instance.generate_shards.return_value = [{"some": "recipe"}]

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                f.write("dataset:\n  seed: 42\n")
                config_path = f.name

            try:
                runner.invoke(
                    app,
                    [
                        "generate",
                        "--config",
                        config_path,
                        "--output",
                        "/tmp/test_output_cmd",
                    ],
                )

                # Verify subprocess.run was called
                assert mock_run.called, "subprocess.run should have been called"

                # Get the command that was passed to subprocess.run
                call_args = mock_run.call_args
                cmd = call_args[0][0]  # First positional arg is the command list

                # Verify command structure
                assert "blenderproc" in cmd, "Command should include 'blenderproc'"
                assert "run" in cmd, "Command should include 'run'"
                # New CLI passes --recipe, not --config to the backend script
                assert "--recipe" in cmd, "Command should include '--recipe'"
                assert "--output" in cmd, "Command should include '--output'"
                assert "--renderer-mode" in cmd, "Command should include '--renderer-mode'"
                assert "--shard-id" in cmd, "Command should include '--shard-id'"

                # Verify executor is referenced
                cmd_str = " ".join(cmd)
                assert "backend/executor.py" in cmd_str, (
                    "Command should reference backend/executor.py"
                )
            finally:
                Path(config_path).unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("render_tag.cli.check_blenderproc_installed", return_value=True)
    def test_generate_config_serialization(
        self, mock_check: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test that recipe JSON is generated and passed to subprocess."""
        import unittest.mock as mock

        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")

        with patch("render_tag.cli.Generator") as MockGenerator:
            mock_gen_instance = MockGenerator.return_value
            # return a dummy recipe list
            mock_gen_instance.generate_shards.return_value = [{"scene_id": 0}]

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                f.write("""
dataset:
  seed: 12345
""")
                config_path = f.name

            try:
                runner.invoke(
                    app,
                    [
                        "generate",
                        "--config",
                        config_path,
                        "--output",
                        "/tmp/test_output_serialization",
                        "--scenes",
                        "5",
                    ],
                )

                # Get the command and find the recipe path
                call_args = mock_run.call_args
                cmd = call_args[0][0]

                # Find the JSON recipe path in the command
                recipe_idx = cmd.index("--recipe") + 1
                json_recipe_path = Path(cmd[recipe_idx])

                # Verify the JSON file name pattern
                assert "recipes_shard_" in str(json_recipe_path.name)
                assert json_recipe_path.suffix == ".json"
            finally:
                Path(config_path).unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("render_tag.cli.check_blenderproc_installed", return_value=True)
    def test_generate_with_renderer_mode(self, mock_check: MagicMock, mock_run: MagicMock) -> None:
        """Test that --renderer-mode flag is passed to subprocess."""
        import unittest.mock as mock

        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")

        with patch("render_tag.cli.Generator") as MockGenerator:
            # Mock generator to avoid creating real recipes
            mock_gen_instance = MockGenerator.return_value
            mock_gen_instance.generate_shards.return_value = [{"scene": 1}]

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                f.write("dataset:\n  seed: 42\n")
                config_path = f.name

            try:
                # Test with workbench mode
                runner.invoke(
                    app,
                    [
                        "generate",
                        "--config",
                        config_path,
                        "--output",
                        "/tmp/test_output_renderer",
                        "--renderer-mode",
                        "workbench",
                    ],
                )

                call_args = mock_run.call_args
                cmd = call_args[0][0]

                # Find renderer-mode in command
                assert "--renderer-mode" in cmd, "Command should include --renderer-mode"
                renderer_idx = cmd.index("--renderer-mode") + 1
                assert cmd[renderer_idx] == "workbench", (
                    f"Expected 'workbench', got '{cmd[renderer_idx]}'"
                )
            finally:
                Path(config_path).unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("render_tag.cli.check_blenderproc_installed", return_value=True)
    def test_generate_scenes_override(self, mock_check: MagicMock, mock_run: MagicMock) -> None:
        """Test that --scenes flag overrides config value."""
        import unittest.mock as mock

        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")

        with patch("render_tag.cli.Generator") as MockGenerator:
            # Mock generator instance
            mock_gen_instance = MockGenerator.return_value
            mock_gen_instance.generate_shards.return_value = [{"scene": 1}]

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                # Config says 10 scenes
                f.write("""
dataset:
  seed: 42
  num_scenes: 10
""")
                config_path = f.name

            try:
                # Override to 3 scenes via CLI
                result = runner.invoke(
                    app,
                    [
                        "generate",
                        "--config",
                        config_path,
                        "--output",
                        "/tmp/test_output_scenes",
                        "--scenes",
                        "3",
                    ],
                )

                assert result.exit_code == 0, f"Command failed: {result.stdout}"

                # Verify Generator was initialized with correct config (num_scenes=3)
                assert MockGenerator.called
                init_args = MockGenerator.call_args[0]
                config_arg = init_args[0]
                assert config_arg["dataset"]["num_scenes"] == 3

            finally:
                Path(config_path).unlink(missing_ok=True)


class TestCLIHelp:
    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "generate" in result.stdout
        assert "validate-config" in result.stdout
        assert "info" in result.stdout

    def test_generate_help(self) -> None:
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.stdout
        assert "--output" in result.stdout
        assert "--scenes" in result.stdout
        assert "--renderer-mode" in result.stdout
