import os
import sys
from unittest.mock import MagicMock, patch

from render_tag.backend.bootstrap import setup_environment


def test_bootstrap_exists():
    """Verify that the bootstrap module can be imported."""
    import render_tag.backend.bootstrap

    assert render_tag.backend.bootstrap is not None


def test_setup_environment_adds_src_to_path():
    """Verify that setup_environment adds the project src directory to sys.path."""
    # We need to make sure we don't pollute the real sys.path
    with (
        patch("sys.path", sys.path.copy()),
        patch("site.addsitedir"),
        patch.dict(sys.modules, {"pydantic": MagicMock()}),
    ):
        setup_environment()

        # Check if a path ending in src is in sys.path
        found = any(p.endswith("src") for p in sys.path)
        assert found, f"src directory not found in sys.path: {sys.path}"


def test_setup_environment_uses_env_var(tmp_path):
    """Verify that setup_environment uses RENDER_TAG_VENV_SITE_PACKAGES if set."""
    # Implementation now checks for pythonX.Y/site-packages structure
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    dummy_site = tmp_path / "lib" / python_version / "site-packages"
    dummy_site.mkdir(parents=True)

    with (
        patch("sys.path", sys.path.copy()),
        patch("site.addsitedir") as mock_addsitedir,
        patch.dict(os.environ, {"RENDER_TAG_VENV_SITE_PACKAGES": str(dummy_site)}),
        patch.dict(sys.modules, {"pydantic": MagicMock(), "orjson": MagicMock()}),
    ):
        setup_environment()
        mock_addsitedir.assert_any_call(str(dummy_site))


def test_setup_environment_fallback_to_venv(tmp_path):
    """Verify that setup_environment falls back to searching for .venv."""
    # Create a mock project structure
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").touch()

    src_dir = project_root / "src"
    src_dir.mkdir()
    backend_dir = src_dir / "render_tag" / "backend"
    backend_dir.mkdir(parents=True)

    # Create a mock .venv site-packages matching CURRENT python version to pass guard
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    if sys.platform == "win32":
        venv_site = project_root / ".venv" / "Lib" / "site-packages"
    else:
        venv_site = project_root / ".venv" / "lib" / python_version / "site-packages"

    venv_site.mkdir(parents=True)

    # Mock __file__ of the bootstrap module
    mock_bootstrap_file = backend_dir / "bootstrap.py"

    with (
        patch("sys.path", sys.path.copy()),
        patch("site.addsitedir") as mock_addsitedir,
        patch("render_tag.backend.bootstrap.__file__", str(mock_bootstrap_file)),
        patch.dict(os.environ, {}, clear=True),
        patch.dict(sys.modules, {"pydantic": MagicMock(), "orjson": MagicMock()}),
    ):
        setup_environment()
        # It should have found and added the venv site-packages
        mock_addsitedir.assert_any_call(str(venv_site))


def test_setup_environment_fails_fast(caplog):
    """Verify that setup_environment logs warning if pydantic is missing."""
    import logging

    with (
        patch("sys.path", sys.path.copy()),
        patch("site.addsitedir"),
        patch.dict(sys.modules, {"pydantic": None, "orjson": None}),
        patch("render_tag.backend.bootstrap.configure_logging"),
        caplog.at_level(logging.WARNING),
    ):
        setup_environment()
        assert "Bootstrap: Critical dependencies missing" in caplog.text
