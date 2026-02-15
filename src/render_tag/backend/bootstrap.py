import contextlib
import os
import site
import sys
from pathlib import Path

from render_tag.core.utils import find_venv_site_packages, get_project_root, get_venv_site_packages


def setup_environment():
    """
    Stabilizes the environment for the Blender Python backend.
    Ensures 'src' is in sys.path and venv site-packages are loaded if running inside Blender.
    """
    root = get_project_root()
    src_dir = str(root / "src")
    repo_root = str(root)

    # 1. Ensure the 'src' directory is in sys.path
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # 2. Add repo root to sys.path
    if repo_root not in sys.path:
        sys.path.append(repo_root)

    # 3. Handle Blender's internal Python: Add project venv site-packages
    # Precedence: Env Var > .venv in repo root > Current active venv
    venv_site_packages = (
        os.environ.get("RENDER_TAG_VENV_SITE_PACKAGES")
        or find_venv_site_packages(root)
        or get_venv_site_packages()
    )

    if venv_site_packages:
        # Avoid mixing incompatible python versions
        venv_version_dir = Path(venv_site_packages).parent.name  # 'python3.10'
        blender_version_str = f"python{sys.version_info.major}.{sys.version_info.minor}"

        if venv_version_dir == blender_version_str:
            site.addsitedir(venv_site_packages)

    # 4. Stabilize dependencies via BlenderBridge
    from render_tag.backend.bridge import bridge

    bridge.stabilize()

    # 5. Configure structured logging
    with contextlib.suppress(Exception):
        configure_logging()

    # 5. Verify critical dependencies
    try:
        import orjson  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError as e:
        # We don't raise here to allow the caller to handle it (or use mocks)
        # but we do log it.
        import logging

        logging.getLogger(__name__).warning(f"Bootstrap: Critical dependencies missing: {e}")


def configure_logging():
    """Configures structured JSON logging for the backend."""
    try:
        from render_tag.core.logging import setup_logging

        # In backend, we prefer JSON format if not specified otherwise
        if "LOG_FORMAT" not in os.environ:
            os.environ["LOG_FORMAT"] = "json"

        setup_logging()
    except ImportError:
        # Fallback to basic if render_tag dependencies aren't available
        import logging

        logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    setup_environment()
