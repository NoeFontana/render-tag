"""
Tests for CI configuration.
"""

from pathlib import Path
import yaml


def test_ci_file_exists():
    """Verify that .github/workflows/ci.yml exists."""
    ci_file = Path(".github/workflows/ci.yml")
    assert ci_file.exists(), "CI workflow file not found."


def test_ci_file_is_valid_yaml():
    """Verify that .github/workflows/ci.yml is a valid YAML file."""
    ci_file = Path(".github/workflows/ci.yml")
    if not ci_file.exists():
        return  # Covered by test_ci_file_exists
        
    with open(ci_file, "r") as f:
        try:
            yaml.safe_load(f)
        except yaml.YAMLError as exc:
            assert False, f"CI file is not a valid YAML: {exc}"
