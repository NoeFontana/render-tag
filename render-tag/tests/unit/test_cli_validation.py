import pytest
from typer.testing import CliRunner
from render_tag.cli import app
from pathlib import Path

runner = CliRunner()

def test_cli_catches_validation_error(tmp_path):
    # Create invalid config
    config_path = tmp_path / "invalid.yaml"
    # Pydantic v2 validation error for int gt=0
    config_path.write_text("dataset:\n  num_scenes: -5\n") 
    
    result = runner.invoke(app, ["generate", "--config", str(config_path)])
    
    assert result.exit_code == 1
    # Check for formatted output
    assert "Validation Error" in result.stdout
    # Check for Pydantic error message part
    assert "Input should be greater than 0" in result.stdout
    
    # Check for rich formatting (custom)
    assert "Validation Error" in result.stdout
