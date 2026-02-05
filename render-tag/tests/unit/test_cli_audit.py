import pytest
from typer.testing import CliRunner
from render_tag.cli import app
from pathlib import Path
import csv
import json

runner = CliRunner()

@pytest.fixture
def dummy_dataset(tmp_path):
    """Creates a minimal dummy dataset for CLI testing."""
    dataset_dir = tmp_path / "dataset_v1"
    dataset_dir.mkdir()
    
    tags_path = dataset_dir / "tags.csv"
    with open(tags_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "tag_id", "tag_family", "x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"])
        writer.writerow(["img1", "0", "family", "0", "0", "1", "0", "1", "1", "0", "1"])
        
    # No manifest or images yet, just minimal tags.csv
    return dataset_dir

def test_audit_command_exists(dummy_dataset):
    """Verify that the audit command is registered and runs."""
    result = runner.invoke(app, ["audit", str(dummy_dataset)])
    # It should fail with Not Implemented or similar if I haven't added it yet
    # Or just fail if it's not in the app
    assert result.exit_code == 0
    assert "AUDIT REPORT" in result.stdout

def test_audit_command_fails_on_missing_dir():
    """Verify that audit fails if the directory doesn't exist."""
    result = runner.invoke(app, ["audit", "non_existent_dir"])
    assert result.exit_code != 0
