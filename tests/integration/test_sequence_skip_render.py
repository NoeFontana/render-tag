import json
import subprocess
import sys

import pytest


def test_sequence_skip_render_generates_ordered_recipe(tmp_path):
    """Sequence configs should generate ordered camera recipes without invoking Blender."""
    config_path = tmp_path / "sequence_config.yaml"
    config_path.write_text(
        """
dataset:
  num_scenes: 1
camera:
  resolution: [64, 64]
  samples_per_scene: 1
  min_distance: 0.8
  max_distance: 1.0
  sensor_dynamics:
    blur_profile: light
    shutter_time_ms: 6.0
scenario:
  subject:
    type: TAGS
    tag_families: [tag36h11]
    size_mm: 120.0
    tags_per_scene: 1
sequence:
  enabled: true
  frames_per_sequence: 3
  fps: 15
  max_translation_per_frame_m: 0.01
"""
    )
    output_dir = tmp_path / "out"

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
            "--skip-render",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    with open(output_dir / "recipes_shard_0.json") as f:
        recipes = json.load(f)

    cameras = recipes[0]["cameras"]
    assert [cam["frame_index"] for cam in cameras] == [0, 1, 2]
    assert [cam["timestamp_s"] for cam in cameras] == pytest.approx(
        [0.003, (1.0 / 15.0) + 0.003, (2.0 / 15.0) + 0.003]
    )
    assert cameras[0]["sensor_dynamics"]["blur_profile"] == "light"
    assert cameras[1]["sensor_dynamics"]["velocity"] is not None
