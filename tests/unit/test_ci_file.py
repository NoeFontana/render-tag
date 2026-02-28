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


def test_ci_file_contains_ruff_format():
    """Verify that .github/workflows/ci.yml contains the ruff format step."""
    ci_file = Path(".github/workflows/ci.yml")
    if not ci_file.exists():
        return
        
    with open(ci_file, "r") as f:
        config = yaml.safe_load(f)
        steps = config["jobs"]["quality-gates"]["steps"]
        ruff_format_step = next((s for s in steps if "ruff format" in s.get("run", "")), None)
        assert ruff_format_step is not None, "Ruff format step not found in CI workflow."


def test_ci_file_contains_ruff_check():
    """Verify that .github/workflows/ci.yml contains the ruff check step."""
    ci_file = Path(".github/workflows/ci.yml")
    if not ci_file.exists():
        return
        
    with open(ci_file, "r") as f:
        config = yaml.safe_load(f)
        steps = config["jobs"]["quality-gates"]["steps"]
        ruff_check_step = next((s for s in steps if "ruff check" in s.get("run", "")), None)
        assert ruff_check_step is not None, "Ruff check step not found in CI workflow."


def test_ci_file_contains_lint_arch():
    """Verify that .github/workflows/ci.yml contains the lint-arch step."""
    ci_file = Path(".github/workflows/ci.yml")
    if not ci_file.exists():
        return
        
    with open(ci_file, "r") as f:
        config = yaml.safe_load(f)
        steps = config["jobs"]["quality-gates"]["steps"]
        lint_arch_step = next((s for s in steps if "lint-arch" in s.get("run", "")), None)
        assert lint_arch_step is not None, "Lint arch step not found in CI workflow."


def test_ci_file_contains_ty_check():
    """Verify that .github/workflows/ci.yml contains the ty check step."""
    ci_file = Path(".github/workflows/ci.yml")
    if not ci_file.exists():
        return
        
    with open(ci_file, "r") as f:
        config = yaml.safe_load(f)
        steps = config["jobs"]["quality-gates"]["steps"]
        ty_check_step = next((s for s in steps if "ty check" in s.get("run", "")), None)
        assert ty_check_step is not None, "Ty check step not found in CI workflow."
