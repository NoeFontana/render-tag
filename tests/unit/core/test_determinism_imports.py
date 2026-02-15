import pytest
import subprocess

def test_generation_layer_cannot_import_random():
    """Verify that the import linter blocks 'random' in the generation package."""
    # We run the command and check the output for the specific failure
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        capture_output=True,
        text=True
    )
    
    # It should fail because we haven't removed the imports yet
    assert result.returncode != 0
    assert "Determinism enforcement (Generation) BROKEN" in result.stdout
    assert "render_tag.generation is not allowed to import random" in result.stdout
