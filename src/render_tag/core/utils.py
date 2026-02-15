import os
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
    prefix = Path(sys.prefix) if prefix is None else Path(prefix)

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


def get_subprocess_env(
    base_env: dict[str, str] | None = None,
    thread_budget: int = 1,
    job_id: str | None = None,
    mock: bool = False,
) -> dict[str, str]:
    """
    Constructs a standardized environment dictionary for subprocesses (workers).

    Handles PYTHONPATH injection, venv site-packages propagation, and thread limits.
    """
    env = base_env.copy() if base_env else os.environ.copy()
    root = get_project_root()

    # 1. Inject Source Paths
    src_path = str(root / "src")
    repo_root = str(root)
    curr_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_path}{os.pathsep}{repo_root}{os.pathsep}{curr_pp}".strip(os.pathsep)

    # 2. Python Configuration
    env["PYTHONNOUSERSITE"] = "1"
    env["OMP_NUM_THREADS"] = str(thread_budget)
    env["BLENDER_CPU_THREADS"] = str(thread_budget)

    # 3. Propagate Virtual Environment
    # This is used by the backend bootstrap to inject site-packages
    venv_site = get_venv_site_packages()
    if venv_site:
        env["RENDER_TAG_VENV_SITE_PACKAGES"] = venv_site

    # 4. Render Tag Specifics
    if job_id:
        env["RENDER_TAG_JOB_ID"] = job_id

    if mock:
        env["RENDER_TAG_BACKEND_MOCK"] = "1"
        env["OUTSIDE_OF_THE_INTERNAL_BLENDER_PYTHON_ENVIRONMENT_BUT_IN_RUN_SCRIPT"] = "1"

    return env
