import os
import site
import sys
from pathlib import Path


def setup_environment():
    """
    Synchronizes the Blender Python environment with the project virtual environment.
    """
    # Staff Engineer: Robustly find project root (directory containing 'render_tag')
    # 1. Check environment variable first (most reliable in orchestrated mode)
    src_dir = os.environ.get("RENDER_TAG_SRC_ROOT")
    
    if not src_dir:
        # 2. Fallback: Search upwards from this file
        _curr = Path(__file__).resolve().parent
        while _curr.parent != _curr:
            if (_curr / "render_tag").is_dir() and (_curr / "render_tag" / "__init__.py").exists():
                src_dir = str(_curr.parent)
                break
            _curr = _curr.parent
            
    if not src_dir:
        # 3. Last fallback: parents[2]
        src_dir = str(Path(__file__).resolve().parents[2])

    if src_dir and src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # 2. Orchestration Mode: Get site-packages from environment variable
    venv_site_packages = os.environ.get("RENDER_TAG_VENV_SITE_PACKAGES")

    # 3. Dev Mode Fallback: Search for .venv if not provided by orchestrator
    if not venv_site_packages:
        project_root = Path(src_dir).parent if src_dir else Path.cwd()
        venv_path = project_root / ".venv"

        if venv_path.exists():
            if sys.platform == "win32":
                potential_site = venv_path / "Lib" / "site-packages"
            else:
                lib_dir = venv_path / "lib"
                if lib_dir.exists():
                    sites = list(lib_dir.glob("python*/site-packages"))
                    potential_site = sites[0] if sites else None
                else:
                    potential_site = None

            if potential_site and potential_site.exists():
                venv_site_packages = str(potential_site)

    if venv_site_packages:
        venv_version_dir = Path(venv_site_packages).parent.name
        blender_version_str = f"python{sys.version_info.major}.{sys.version_info.minor}"

        if venv_version_dir == blender_version_str:
            site.addsitedir(venv_site_packages)

    # 4. Configure Structured Logging
    try:
        configure_logging()
    except Exception:
        pass

    # 5. Fail Fast: Verify critical dependencies
    try:
        import orjson  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            f"Blender Environment Bootstrap Failed.\n"
            f"Critical dependency not found: {e}\n"
        ) from e


def configure_logging():
    """Configures structured JSON logging for the Blender backend."""
    import logging
    try:
        from render_tag.core.logging import JSONFormatter
    except ImportError:
        # If we still can't find it, we can't configure structured logging yet
        return

    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


if __name__ == "__main__":
    setup_environment()
