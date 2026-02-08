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

from render_tag.cli.tools import check_blenderproc_installed

# Skip all tests in this file if blenderproc is not installed
pytestmark = pytest.mark.skipif(
    not check_blenderproc_installed(), reason="BlenderProc is not installed"
)


@pytest.mark.integration
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
  resolution: [128, 128]
  fov: 60.0
  samples_per_scene: 1
tag:
  family: tag36h11
  size_meters: 0.05
scene:
  background_hdri: null
  texture_dir: null
physics:
  drop_height: 0.5
  scatter_radius: 0.1
"""
        config_path = temp_output_dir / "test_config.yaml"
        config_path.write_text(config_content)
        return config_path

    def test_full_pipeline_consistency(self, temp_output_dir, minimal_config):
        """
        Consolidated test that verifies output structure, CSV format, and COCO format 
        in a single render run using the fast Workbench renderer.
        """
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
                "5",
                "--renderer-mode",
                "workbench"
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        # 1. Check command succeeded
        if result.returncode != 0:
            print(result.stdout)
        assert result.returncode == 0, f"Generation failed: {result.stderr}"
    
        # 2. Check output structure
        print(result.stdout)
        assert output_dir.exists()

        
        assert (output_dir / "images").exists()
        assert (output_dir / "tags.csv").exists()
        assert (output_dir / "annotations.json").exists()
        assert (output_dir / "images/scene_0000_cam_0000.png").exists()

        # 3. Check CSV format
        csv_path = output_dir / "tags.csv"
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) >= 1
        expected_fields = [
            "image_id", "tag_id", "tag_family", 
            "x1", "y1", "x2", "y2", 
            "x3", "y3", "x4", "y4"
        ]
        assert reader.fieldnames is not None
        assert all(f in reader.fieldnames for f in expected_fields)

        # 4. Check COCO format
        coco_path = output_dir / "annotations.json"
        with open(coco_path) as f:
            coco_data = json.load(f)
        
        assert "images" in coco_data
        assert "annotations" in coco_data
        assert len(coco_data["images"]) >= 1
        assert coco_data["images"][0]["width"] == 128

    def test_generate_skip_render(self, temp_output_dir, minimal_config):
        """Test that --skip-render generates recipes without Blender."""
        output_dir = temp_output_dir / "fast_output"

        result = subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(minimal_config),
                "--output",
                str(output_dir),
                "--skip-render",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Skipping Blender launch" in result.stdout
        assert (output_dir / "recipes_shard_0.json").exists()


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
                ["render-tag", "validate-config", "--config", config_path],
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
                ["render-tag", "validate-config", "--config", config_path],
                capture_output=True,
                text=True,
            )

            assert result.returncode != 0
        finally:
            Path(config_path).unlink(missing_ok=True)