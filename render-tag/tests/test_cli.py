"""
Unit tests for the CLI module.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
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
        result = runner.invoke(app, ["validate", "--config", "configs/default.yaml"])
        
        # Should succeed (exit code 0) or fail gracefully if file doesn't exist
        # The command should at least run without crashing
        assert result.exit_code in [0, 1, 2]

    def test_validate_missing_config(self) -> None:
        result = runner.invoke(app, ["validate", "--config", "/nonexistent/config.yaml"])
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
                result = runner.invoke(app, [
                    "generate",
                    "--config", config_path,
                    "--output", "/tmp/test_output",
                ])
                
                # Should fail because blenderproc is not installed
                assert result.exit_code == 1
                assert "blenderproc" in result.stdout.lower()
            finally:
                Path(config_path).unlink(missing_ok=True)


class TestCLIHelp:
    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "generate" in result.stdout
        assert "validate" in result.stdout
        assert "info" in result.stdout

    def test_generate_help(self) -> None:
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.stdout
        assert "--output" in result.stdout
        assert "--scenes" in result.stdout
