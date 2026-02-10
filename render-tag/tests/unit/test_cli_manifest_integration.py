from typer.testing import CliRunner

from render_tag.cli.main import app

runner = CliRunner()


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

    import shutil

    monkeypatch.setattr(shutil, "which", lambda x: None)

    # Run command with --skip-render
    result = runner.invoke(
        app,
        ["generate", "--config", str(config_file), "--output", str(output_dir), "--skip-render"],
    )

    print(result.output)
    assert result.exit_code == 0
    assert (output_dir / "manifest.json").exists()
    assert "Generating dataset manifest" in result.output
