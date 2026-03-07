from typer.testing import CliRunner

from render_tag.cli.main import app

runner = CliRunner()

def test_viz_fiftyone_command_exists():
    """Test that 'render-tag viz fiftyone' command exists and shows help."""
    result = runner.invoke(app, ["viz", "fiftyone", "--help"])
    assert result.exit_code == 0
    assert "Visualize a dataset with Voxel51 FiftyOne" in result.output
    assert "--dataset" in result.output

def test_viz_fiftyone_requires_dataset():
    """Test that 'render-tag viz fiftyone' fails if --dataset is missing."""
    result = runner.invoke(app, ["viz", "fiftyone"])
    assert result.exit_code != 0
    assert "Missing option '--dataset'" in result.output or "Error: Missing option" in result.output
