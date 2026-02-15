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


def get_project_root() -> Path:
    """Returns the root directory of the project."""
    # Find the directory containing pyproject.toml
    curr = Path(__file__).resolve().parent
    while curr.parent != curr:
        if (curr / "pyproject.toml").exists():
            return curr
        curr = curr.parent
    # Fallback to current working directory if not found
    return Path.cwd()


def get_venv_site_packages(prefix: Path | str | None = None) -> str | None:
    """
    Detects the site-packages directory of a virtual environment.
    If prefix is None, uses sys.prefix (active venv).
    """
    if prefix is None:
        prefix = Path(sys.prefix)
    else:
        prefix = Path(prefix)

    prefix = prefix.resolve()

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


def find_venv_site_packages(root: Path | str) -> str | None:
    """Looks for a .venv directory in the root and returns its site-packages path."""
    potential_venv = Path(root) / ".venv"
    if potential_venv.exists():
        return get_venv_site_packages(potential_venv)
    return None
