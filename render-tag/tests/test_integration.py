"""
Integration tests for the full render-tag pipeline.

Note: These tests require BlenderProc to be installed and will be skipped
if BlenderProc is not available.
"""

import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from render_tag.cli import check_blenderproc_installed


# Skip all tests in this file if blenderproc is not installed
pytestmark = pytest.mark.skipif(
    not check_blenderproc_installed(), reason="BlenderProc is not installed"
)


class TestFullPipeline:
    """Integration tests that run the complete generation pipeline."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        tmpdir = tempfile.mkdtemp(prefix="render_tag_test_")
        yield Path(tmpdir)
        # Cleanup
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def minimal_config(self, temp_output_dir):
        """Create a minimal config file for testing."""
        config_content = """
dataset:
  seed: 42
  num_scenes: 1
camera:
  resolution: [100, 100]
  fov: 60.0
  samples_per_scene: 1
tag:
  family: tag36h11
  size_meters: 0.05
physics:
  drop_height: 0.5
  scatter_radius: 0.1
"""
        config_path = temp_output_dir / "test_config.yaml"
        config_path.write_text(config_content)
        return config_path

    def test_generate_creates_output_directory(self, temp_output_dir, minimal_config):
        """Test that generation creates the expected output structure."""
        output_dir = temp_output_dir / "output"

        result = subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(minimal_config),
                "--output",
                str(output_dir),
                "--scenes",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        # Check command succeeded
        assert result.returncode == 0, f"Generation failed: {result.stderr}"

        # Check output structure
        assert output_dir.exists(), "Output directory was not created"
        assert (output_dir / "images").exists(), "Images directory was not created"
        assert (output_dir / "tags.csv").exists(), "CSV file was not created"
        assert (output_dir / "annotations.json").exists(), "COCO file was not created"

    def test_csv_has_valid_format(self, temp_output_dir, minimal_config):
        """Test that generated CSV has valid format and values."""
        output_dir = temp_output_dir / "output"

        result = subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(minimal_config),
                "--output",
                str(output_dir),
                "--scenes",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Generation failed: {result.stderr}"

        csv_path = output_dir / "tags.csv"
        assert csv_path.exists()

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have at least one detection
        assert len(rows) >= 1, "CSV should have at least one detection"

        # Check header fields
        expected_fields = [
            "image_id",
            "tag_id",
            "tag_family",
            "x1",
            "y1",
            "x2",
            "y2",
            "x3",
            "y3",
            "x4",
            "y4",
        ]
        assert all(f in reader.fieldnames for f in expected_fields), (
            "Missing CSV fields"
        )

        # Check values are within image bounds (100x100)
        for row in rows:
            for coord in ["x1", "x2", "x3", "x4"]:
                x = float(row[coord])
                assert 0 <= x <= 100, f"X coordinate {x} out of bounds"

            for coord in ["y1", "y2", "y3", "y4"]:
                y = float(row[coord])
                assert 0 <= y <= 100, f"Y coordinate {y} out of bounds"

    def test_coco_has_valid_format(self, temp_output_dir, minimal_config):
        """Test that generated COCO JSON has valid format."""
        output_dir = temp_output_dir / "output"

        result = subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(minimal_config),
                "--output",
                str(output_dir),
                "--scenes",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Generation failed: {result.stderr}"

        coco_path = output_dir / "annotations.json"
        assert coco_path.exists()

        with open(coco_path) as f:
            coco_data = json.load(f)

        # Check required COCO fields
        assert "images" in coco_data
        assert "annotations" in coco_data
        assert "categories" in coco_data

        # Check at least one of each
        assert len(coco_data["images"]) >= 1
        assert len(coco_data["categories"]) >= 1

        # Check image structure
        for img in coco_data["images"]:
            assert "id" in img
            assert "file_name" in img
            assert "width" in img
            assert "height" in img
            assert img["width"] == 100
            assert img["height"] == 100

        # Check annotation structure
        for ann in coco_data["annotations"]:
            assert "id" in ann
            assert "image_id" in ann
            assert "category_id" in ann
            assert "segmentation" in ann
            assert "bbox" in ann
            assert len(ann["bbox"]) == 4


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_valid_config(self):
        """Test validation of a valid config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
dataset:
  seed: 42
camera:
  resolution: [640, 480]
tag:
  family: tag36h11
""")
            config_path = f.name

        try:
            result = subprocess.run(
                ["render-tag", "validate", "--config", config_path],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert "valid" in result.stdout.lower()
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_validate_invalid_config(self):
        """Test validation of an invalid config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
dataset:
  seed: -1  # Invalid: negative seed
""")
            config_path = f.name

        try:
            result = subprocess.run(
                ["render-tag", "validate", "--config", config_path],
                capture_output=True,
                text=True,
            )

            assert result.returncode != 0
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestInfoCommand:
    """Tests for the info command (doesn't require BlenderProc)."""

    @pytest.mark.skip(reason="Already covered in test_cli.py")
    def test_info_shows_tag_families(self):
        """Test that info command shows tag families."""
        result = subprocess.run(
            ["render-tag", "info"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "AprilTag" in result.stdout
        assert "ArUco" in result.stdout
