"""
Integration test for Coordinate System Synchronization (Y-Axis Inversion).
Generates an asymmetric board (2x7) and verifies Top-Down orientation.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from render_tag.cli.tools import check_blenderproc_installed

# Skip if BlenderProc is not installed
pytestmark = pytest.mark.skipif(
    not check_blenderproc_installed(), reason="BlenderProc is not installed"
)

@pytest.mark.integration
class TestOrientationContract:
    """Verify that Row 0 is at the Top and Marker 0 is at Top-Left."""

    @pytest.fixture
    def output_dir(self, tmp_path):
        """Create a temporary output directory."""
        d = tmp_path / "orientation_test"
        d.mkdir()
        return d

    @pytest.fixture
    def asymmetric_config(self, output_dir):
        """Create a config for an asymmetric 2x7 AprilGrid board."""
        config = {
            "version": "0.2",
            "dataset": {"seed": 100, "num_scenes": 1},
            "camera": {
                "resolution": [640, 480],
                "fov": 60.0,
                "samples_per_scene": 1,
                # Fixed camera looking directly at origin
                "min_distance": 1.0,
                "max_distance": 1.0,
                "min_elevation": 0.99, # Directly above
                "max_elevation": 1.0,
            },
            "scenario": {
                "subject": {
                    "type": "BOARD",
                    "rows": 2,
                    "cols": 7,
                    "marker_size": 0.05,
                    "spacing_ratio": 0.2,
                    "dictionary": "tag36h11"
                }
            },
            "scene": {
                "background_hdri": None,
                "texture_dir": None
            },
            "physics": {
                "scatter_radius": 0.001 # Must be > 0
            }
        }
        config_path = output_dir / "asymmetric_board.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)
        return config_path

    def test_asymmetric_board_orientation(self, output_dir, asymmetric_config):
        """Generate a 2x7 board and verify its orientation."""
        # 1. Run generation
        import os
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path.cwd() / "src")
        # Ensure .venv/bin is in PATH for blenderproc
        venv_bin = str(Path.cwd() / ".venv" / "bin")
        env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
        
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "render_tag",
                "generate",
                "--config", str(asymmetric_config),
                "--output", str(output_dir),
                "--renderer-mode", "workbench", # Fast renderer
                "--scenes", "1"
            ],
            capture_output=True,
            text=True,
            env=env
        )
        assert result.returncode == 0, f"Generation failed: {result.stderr}"

        # 2. Check 3D Keypoints from Recipe
        recipe_path = output_dir / "recipes_shard_0.json"
        with open(recipe_path) as f:
            recipes = json.load(f)
        
        board_obj = next(obj for obj in recipes[0]["objects"] if obj["type"] == "BOARD")
        kps_3d = board_obj["keypoints_3d"]
        
        # In a 2x7 AprilGrid, we have 14 tags.
        # layout.tag_positions has 14 points.
        # BoardStrategy.sample_pose adds 4 corners per tag.
        # So kps_3d[:4] are corners of Tag 0 (Row 0, Col 0).
        # kps_3d[4:8] are corners of Tag 1 (Row 0, Col 1).
        
        # Row 0 tags should have higher Y than Row 1 tags.
        # Tag 0 (Row 0) center Y: (kps_3d[0][1] + kps_3d[2][1]) / 2
        # Tag 7 (Row 1, Col 0) center Y: (kps_3d[28][1] + kps_3d[30][1]) / 2
        
        tag0_y = (kps_3d[0][1] + kps_3d[2][1]) / 2.0
        tag7_y = (kps_3d[28][1] + kps_3d[30][1]) / 2.0
        
        assert tag0_y > tag7_y, f"Tag 0 Y ({tag0_y}) should be above Tag 7 Y ({tag7_y})"
        
        # 3. Check Ground Truth (CSV/JSON)
        # Verify that Tag 0 is at the Top-Left in the image.
        csv_path = output_dir / "ground_truth.csv"
        import csv
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            detections = list(reader)
        
        # Find Tag 0
        tag0 = next(d for d in detections if int(d["tag_id"]) == 0)
        tag7 = next(d for d in detections if int(d["tag_id"]) == 7)
        
        # In OpenCV image coords, Y increases DOWN.
        # So Tag 0 (Top row) should have SMALLER Y than Tag 7 (Bottom row).
        y0 = float(tag0["y1"]) # Top-left corner Y
        y7 = float(tag7["y1"]) 
        
        assert y0 < y7, f"Tag 0 Image Y ({y0}) should be above Tag 7 Image Y ({y7})"
        
        # Tag 0 (Col 0) should have smaller X than Tag 1 (Col 1)
        tag1 = next(d for d in detections if int(d["tag_id"]) == 1)
        x0 = float(tag0["x1"])
        x1 = float(tag1["x1"])
        assert x0 < x1, f"Tag 0 Image X ({x0}) should be left of Tag 1 Image X ({x1})"

        print("Orientation Contract Verified Successfully!")
