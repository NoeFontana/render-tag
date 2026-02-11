import hashlib
import json

from typer.testing import CliRunner

from render_tag.cli.main import app

runner = CliRunner()


def test_cli_verify_success(tmp_path):
    # 1. Create a valid dataset with manifest
    output_dir = tmp_path / "dataset"
    output_dir.mkdir()

    csv_file = output_dir / "tags.csv"
    csv_file.write_text("valid content")
    csv_hash = hashlib.sha256(b"valid content").hexdigest()

    manifest_data = {
        "job_id": "job_123",
        "created_at": "2026-01-01T00:00:00Z",
        "files": {"tags.csv": csv_hash},
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest_data, f)

    # 2. Run verify
    result = runner.invoke(app, ["job", "verify", str(output_dir)])

    assert result.exit_code == 0
    assert "Integrity check passed" in result.output


def test_cli_verify_tampered(tmp_path):
    # 1. Create a valid dataset
    output_dir = tmp_path / "dataset_tampered"
    output_dir.mkdir()

    csv_file = output_dir / "tags.csv"
    csv_file.write_text("original content")
    csv_hash = hashlib.sha256(b"original content").hexdigest()

    manifest_data = {"job_id": "job_123", "files": {"tags.csv": csv_hash}}
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest_data, f)

    # 2. Tamper with the file
    csv_file.write_text("tampered content")

    # 3. Run verify
    result = runner.invoke(app, ["job", "verify", str(output_dir)])

    assert result.exit_code != 0
    assert "Integrity check FAILED" in result.output
    assert "tags.csv" in result.output
