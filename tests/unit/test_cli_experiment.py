"""
Unit tests for the experiment CLI.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from render_tag.cli.main import app

runner = CliRunner()


@patch("render_tag.cli.experiment.load_experiment_config")
@patch("render_tag.cli.experiment.expand_experiment")
@patch("render_tag.cli.experiment.check_blenderproc_installed")
@patch("render_tag.cli.experiment.subprocess.run")
@patch("render_tag.cli.experiment.Generator")
@patch("render_tag.cli.experiment.save_manifest")
@patch("render_tag.cli.experiment.serialize_config_to_json")
@patch("render_tag.cli.experiment.ensure_tag_asset")
def test_experiment_run_success(
    mock_ensure,
    mock_serialize,
    mock_manifest,
    mock_generator,
    mock_run,
    mock_check,
    mock_expand,
    mock_load,
    tmp_path: Path,
) -> None:
    mock_check.return_value = True

    # Setup experiment
    exp = MagicMock()
    exp.name = "my_exp"
    mock_load.return_value = exp

    # Setup variants
    v1 = MagicMock()
    v1.variant_id = "v1"
    v1.config = MagicMock()
    v1.config.scenario = None
    v1.config.tag.family = MagicMock(value="tag36h11")
    v1.config.dataset.output_dir = tmp_path
    mock_expand.return_value = [v1]

    # Setup subprocess
    mock_run.return_value = MagicMock(returncode=0)

    config_file = tmp_path / "exp.yaml"
    config_file.write_text("dummy")

    result = runner.invoke(
        app, ["experiment", "run", "--config", str(config_file), "--output", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "Experiment 'my_exp' Completed Successfully!" in result.stdout
    assert mock_run.called
    assert (tmp_path / "my_exp" / "v1").exists()


@patch("render_tag.cli.experiment.check_blenderproc_installed")
def test_experiment_run_no_blenderproc(mock_check, tmp_path: Path) -> None:
    mock_check.return_value = False
    config_file = tmp_path / "exp.yaml"
    config_file.write_text("dummy")

    result = runner.invoke(app, ["experiment", "run", "--config", str(config_file)])
    assert result.exit_code != 0
    assert "blenderproc not installed" in result.stdout
