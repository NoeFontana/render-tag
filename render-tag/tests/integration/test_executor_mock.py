import subprocess
import pytest
from pathlib import Path

def test_generate_with_mock_executor():
    """Verify that the CLI correctly uses the mock executor and exits successfully."""
    # Use the minimal config to pass pre-flight without assets
    config_path = Path(__file__).parents[2] / "configs" / "test_minimal.yaml"
    
    result = subprocess.run(
        [
            "render-tag",
            "generate",
            "--config", str(config_path),
            "--scenes", "1",
            "--executor", "mock"
        ],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Command failed with: {result.stdout}\n{result.stderr}"
    # Mock output goes to logger which typically goes to stderr
    assert "[MOCK] Executing render" in result.stdout or "[MOCK] Executing render" in result.stderr