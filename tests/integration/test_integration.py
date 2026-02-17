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
  background_hdri: "assets/hdri/dummy.exr"
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

        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "render_tag",
                "generate",
                "--config",
                str(minimal_config),
                "--output",
                str(output_dir),
                "--scenes",
                "2",
                "--renderer-mode",
                "workbench",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        # 1. Check command succeeded
        if result.returncode != 0:
            print(result.stdout)
        assert result.returncode == 0, f"Generation failed: {result.stderr}"

        # 2. Check output structure
        print(result.stdout)
        assert output_dir.exists()

        assert (output_dir / "images").exists()
        assert (output_dir / "ground_truth.csv").exists()
        assert (output_dir / "coco_labels.json").exists()
        assert (output_dir / "images/scene_0000_cam_0000.png").exists()

        # 3. Check CSV format
        csv_path = output_dir / "ground_truth.csv"
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 1
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
        assert reader.fieldnames is not None
        assert all(f in reader.fieldnames for f in expected_fields)

        # 4. Check COCO format
        coco_path = output_dir / "coco_labels.json"
        with open(coco_path) as f:
            coco_data = json.load(f)

        assert "images" in coco_data
        assert "annotations" in coco_data
        assert len(coco_data["images"]) >= 1
        assert coco_data["images"][0]["width"] == 128

    def test_generate_skip_render(self, temp_output_dir, minimal_config):
        """Test that --skip-render generates recipes without Blender."""
        output_dir = temp_output_dir / "fast_output"

        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "render_tag",
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
        assert result.returncode == 0
        # Check that recipes were generated
        assert (output_dir / "recipes_shard_0.json").exists()

    def test_industrial_pipeline_cycles(self, temp_output_dir):
        """Test full pipeline with industrial features (Cycles)."""
        config_content = """
dataset:
  seed: 123
camera:
  resolution: [128, 128]
  sensor_noise: {model: salt_and_pepper, amount: 0.05}
  velocity_mean: 1.0
  shutter_time_ms: 10.0
tag:
  material: {randomize: True}
scene:
  background_hdri: "assets/hdri/dummy.exr"
"""
        config_path = temp_output_dir / "industrial.yaml"
        config_path.write_text(config_content)
        output_dir = temp_output_dir / "industrial_out"

        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "render_tag",
                "generate",
                "--config",
                str(config_path),
                "--output",
                str(output_dir),
                "--scenes",
                "1",
                "--renderer-mode",
                "workbench",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert (output_dir / "images/scene_0000_cam_0000.png").exists()
        assert (output_dir / "ground_truth.csv").exists()

    def test_shard_invariance_fast(self, temp_output_dir):
        """Verify that splitting a job into shards does not change recipes."""
        config_path = temp_output_dir / "shard_config.yaml"
        config_path.write_text("scene:\n  background_hdri: null\n  texture_dir: null\n")

        out_single = temp_output_dir / "single"
        subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(config_path),
                "--output",
                str(out_single),
                "--scenes",
                "4",
                "--seed",
                "999",
                "--total-shards",
                "1",
                "--shard-index",
                "0",
                "--skip-render",
            ],
            check=True,
        )

        out_shard0 = temp_output_dir / "shard0"
        out_shard1 = temp_output_dir / "shard1"

        subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(config_path),
                "--output",
                str(out_shard0),
                "--scenes",
                "4",
                "--seed",
                "999",
                "--total-shards",
                "2",
                "--shard-index",
                "0",
                "--skip-render",
            ],
            check=True,
        )

        subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(config_path),
                "--output",
                str(out_shard1),
                "--scenes",
                "4",
                "--seed",
                "999",
                "--total-shards",
                "2",
                "--shard-index",
                "1",
                "--skip-render",
            ],
            check=True,
        )

        with open(out_single / "recipes_shard_0.json") as f:
            recipes_s = json.load(f)
        with open(out_shard0 / "recipes_shard_0.json") as f:
            recipes_m0 = json.load(f)
        with open(out_shard1 / "recipes_shard_1.json") as f:
            recipes_m1 = json.load(f)

        def normalize_recipe(r):
            """Remove environment-specific absolute paths for comparison."""
            if "world" in r and "texture_path" in r["world"]:
                r["world"]["texture_path"] = None
            for obj in r.get("objects", []):
                if "texture_path" in obj:
                    obj["texture_path"] = None
                if "properties" in obj and "texture_base_path" in obj["properties"]:
                    obj["properties"]["texture_base_path"] = None
            return r

        assert recipes_s[0]["scene_id"] == 0
        assert recipes_m0[0]["scene_id"] == 0
        assert normalize_recipe(recipes_s[0]) == normalize_recipe(recipes_m0[0])
        assert recipes_s[2]["scene_id"] == 2
        assert recipes_m1[0]["scene_id"] == 2
        assert normalize_recipe(recipes_s[2]) == normalize_recipe(recipes_m1[0])


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

        import sys

        try:
            result = subprocess.run(
                [sys.executable, "-m", "render_tag", "validate-config", "--config", config_path],
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

        import sys

        try:
            result = subprocess.run(
                [sys.executable, "-m", "render_tag", "validate-config", "--config", config_path],
                capture_output=True,
                text=True,
            )

            assert result.returncode != 0
        finally:
            Path(config_path).unlink(missing_ok=True)
