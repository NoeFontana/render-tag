import json
import subprocess

import pytest


@pytest.mark.integration
def test_provenance_sidecar_generated(tmp_path):
    """Verify that sidecar JSON files are generated with images."""
    output_dir = tmp_path / "output"
    config_path = tmp_path / "safe_config.yaml"
    config_content = (
        "scene:\n  background_hdri: null\n  texture_dir: null\ncamera:\n  resolution: [128, 128]\n"
    )
    config_path.write_text(config_content)

    # Staff Engineer: Retry logic for robustness in parallel CI environments
    max_retries = 3
    for attempt in range(max_retries):
        result = subprocess.run(
            [
                "render-tag",
                "generate",
                "--output",
                str(output_dir),
                "--scenes",
                "1",
                "--config",
                str(config_path),
                "--renderer-mode",
                "workbench",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            break

        if attempt == max_retries - 1:
            assert result.returncode == 0, (
                f"Generation failed after {max_retries} attempts: {result.stderr}"
            )

        import time

        time.sleep(2)

    # Check sidecar
    # Default camera setup usually produces cam_0000
    sidecar_path = output_dir / "images/scene_0000_cam_0000_meta.json"
    assert sidecar_path.exists(), "Sidecar file not found"

    with open(sidecar_path) as f:
        data = json.load(f)
        assert "git_hash" in data
        assert len(data["git_hash"]) >= 7
        assert "timestamp" in data
        assert "recipe_snapshot" in data
        assert data["recipe_snapshot"]["scene_id"] == 0
