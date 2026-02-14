"""
Integration tests for the architectural linter CLI command.
"""

import subprocess
from pathlib import Path


def test_lint_arch_passes_on_clean_codebase():
    """Verify that lint-arch returns 0 on the current codebase."""
    result = subprocess.run(
        ["uv", "run", "render-tag", "lint-arch"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Architectural integrity verified" in result.stdout


def test_lint_arch_fails_on_violation():
    """Verify that lint-arch returns non-zero when a violation is introduced."""
    # Create a "poison" file in orchestration that imports bpy
    # We use a path relative to the repo root
    poison_file = Path("src/render_tag/orchestration/poison.py")
    poison_file.write_text("import bpy\n")

    try:
        result = subprocess.run(
            ["uv", "run", "render-tag", "lint-arch"], capture_output=True, text=True
        )
        assert result.returncode != 0
        assert "Architectural violations detected" in result.stdout
        # import-linter report should contain the module name
        assert "render_tag.orchestration.poison" in result.stdout
        assert "bpy" in result.stdout
    finally:
        # Cleanup the poison file
        if poison_file.exists():
            poison_file.unlink()
