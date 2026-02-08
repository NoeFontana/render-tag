import pytest
from typer.testing import CliRunner
from render_tag.cli.main import app

runner = CliRunner()

def test_cli_lock_help():
    result = runner.invoke(app, ["lock", "--help"])
    assert result.exit_code == 0
    assert "Generate an immutable job.json" in result.output

def test_cli_lock_basic(tmp_path, monkeypatch):
    # Setup dummy config
    config_file = tmp_path / "config.yaml"
    config_file.write_text("dummy: content")
    
    # Mock uv.lock in the current directory (which will be tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("env content")
    (tmp_path / "assets").mkdir()
    
    # We need to mock get_env_fingerprint or blenderproc availability
    # to avoid errors during test
    import shutil
    monkeypatch.setattr(shutil, "which", lambda x: None)
    
    result = runner.invoke(app, ["lock", "--config", str(config_file), "--output", "job.json"])
    assert result.exit_code == 0
    assert (tmp_path / "job.json").exists()
    assert "Job locked successfully" in result.output
