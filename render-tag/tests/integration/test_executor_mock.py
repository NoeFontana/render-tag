import os
import subprocess
from pathlib import Path


def test_generate_with_mock_executor(tmp_path):
    """Verify that the CLI correctly uses the mock executor and exits successfully."""
    # Setup dummy assets to pass pre-flight
    assets_dir = tmp_path / "dummy_assets"
    assets_dir.mkdir()
    for sub in ["hdri", "textures", "tags", "models"]:
        (assets_dir / sub).mkdir()
    (assets_dir / "hdri" / "dummy.exr").touch()

    # Use the minimal config to pass pre-flight without other assets
    config_path = Path(__file__).parents[2] / "configs" / "test_minimal.yaml"

    result = subprocess.run(
        [
            "render-tag",
            "generate",
            "--config",
            str(config_path),
            "--scenes",
            "1",
            "--executor",
            "mock",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "RENDER_TAG_ASSETS_DIR": str(assets_dir)},
    )

    assert result.returncode == 0, f"Command failed with: {result.stdout}\n{result.stderr}"
    # Mock output goes to logger which typically goes to stderr
    assert "[MOCK] Executing render" in result.stdout or "[MOCK] Executing render" in result.stderr
