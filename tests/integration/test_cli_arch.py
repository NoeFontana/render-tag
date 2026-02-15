"""
Integration tests for the architectural linter CLI command.
"""

import subprocess


def test_lint_arch_passes_on_clean_codebase():
    """Verify that lint-arch returns 0 on the current codebase."""
    result = subprocess.run(
        ["uv", "run", "render-tag", "lint-arch"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Architectural integrity verified" in result.stdout
