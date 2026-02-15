import subprocess
import sys
from pathlib import Path


def get_git_hash() -> str:
    """Get the current git commit hash.

    Returns:
        Short git hash or 'unknown' if git command fails.
    """
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode("ascii")
            .strip()
        )
    except Exception:
        return "unknown"


def get_venv_site_packages() -> str | None:
    """
    Detects the site-packages directory of the currently active virtual environment.
    Returns None if not running in a venv.
    """
    # sys.prefix points to the root of the venv when active
    prefix = Path(sys.prefix).resolve()

    site_packages = None
    if sys.platform == "win32":
        site_packages = prefix / "Lib" / "site-packages"
    else:
        # On Linux/Mac, it's lib/pythonX.Y/site-packages
        lib_dir = prefix / "lib"
        if lib_dir.exists():
            # Find pythonX.Y directory
            sites = list(lib_dir.glob("python*/site-packages"))
            if sites:
                site_packages = sites[0]

    if site_packages and site_packages.exists():
        return str(site_packages)

    return None
