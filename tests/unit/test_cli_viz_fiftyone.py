import re

from typer.testing import CliRunner

from render_tag.cli.main import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*[mK]")
    return ansi_escape.sub("", text)


def test_viz_fiftyone_command_exists():
    """Test that 'render-tag viz fiftyone' command exists and shows help."""
    result = runner.invoke(app, ["viz", "fiftyone", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.output)
    assert "Visualize a dataset with Voxel51 FiftyOne" in output
    assert "--dataset" in output


def test_viz_fiftyone_requires_dataset():
    """Test that 'render-tag viz fiftyone' fails if --dataset is missing."""
    result = runner.invoke(app, ["viz", "fiftyone"])
    assert result.exit_code != 0
    output = strip_ansi(result.output)
    assert "Missing option '--dataset'" in output or "Error: Missing option" in output
