import os
import site
import sys
from pathlib import Path


def setup_environment():
    """
    Synchronizes the Blender Python environment with the project virtual environment.

    This ensures that Blender has access to all project dependencies and the
    live code in the src/ directory.
    """
    # 1. Identify project root and src directory
    # bootstrap.py is located at src/render_tag/backend/bootstrap.py
    current_file = Path(__file__).resolve()
    src_dir = current_file.parents[2]

    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    # 2. Orchestration Mode: Get site-packages from environment variable
    venv_site_packages = os.environ.get("RENDER_TAG_VENV_SITE_PACKAGES")

    # 3. Dev Mode Fallback: Search for .venv if not provided by orchestrator
    if not venv_site_packages:
        # Assume the project root is the parent of src/
        project_root = src_dir.parent
        venv_path = project_root / ".venv"

        if venv_path.exists():
            if sys.platform == "win32":
                potential_site = venv_path / "Lib" / "site-packages"
            else:
                # On Linux/Mac, it's lib/pythonX.Y/site-packages
                lib_dir = venv_path / "lib"
                if lib_dir.exists():
                    sites = list(lib_dir.glob("python*/site-packages"))
                    potential_site = sites[0] if sites else None
                else:
                    potential_site = None

            if potential_site and potential_site.exists():
                venv_site_packages = str(potential_site)

    if venv_site_packages:
        # VERSION GUARD: Only add site-packages if Python versions match (major.minor)
        # to avoid "No module named 'orjson.orjson'" or similar binary incompatibilities.
        # Compiled extensions (like orjson, pydantic-core, numpy) are version-specific.
        venv_version_dir = Path(venv_site_packages).parent.name  # e.g. "python3.12"
        blender_version_str = f"python{sys.version_info.major}.{sys.version_info.minor}"

        if venv_version_dir == blender_version_str:
            site.addsitedir(venv_site_packages)
        else:
            # If versions mismatch, we SHOULD NOT add site-packages blindly.
            # However, if we are in a container or a managed environment,
            # the dependencies might already be in Blender's own site-packages.
            pass

    # 4. Configure Structured Logging
    configure_logging()

    # 5. Fail Fast: Verify critical dependencies
    # We check for pydantic as a baseline dependency for the project
    try:
        import orjson  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError as e:
        # Only raise if we think we found a venv but it's broken
        # or if we are clearly in an environment that should have it.
        raise RuntimeError(
            f"Blender Environment Bootstrap Failed.\n"
            f"Critical dependency not found: {e}\n"
            f"Blender Python: {sys.version_info.major}.{sys.version_info.minor}\n"
            f"Detected site-packages: {venv_site_packages}\n"
            f"Please ensure the dependencies are installed for Blender's Python version."
        ) from e


def configure_logging():
    """Configures structured JSON logging for the Blender backend."""
    import logging

    from render_tag.common.logging import JSONFormatter

    # 1. Setup Root Logger
    root = logging.getLogger()
    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # 2. Redirect stderr to the root logger
    class StderrLogger:
        def __init__(self, logger):
            self.logger = logger

        def write(self, buf):
            for line in buf.rstrip().splitlines():
                self.logger.error(line.rstrip())

        def flush(self):
            pass

    sys.stderr = StderrLogger(logging.getLogger("stderr"))


if __name__ == "__main__":
    setup_environment()
