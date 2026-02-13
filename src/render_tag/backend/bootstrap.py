import os
import sys
import site
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
                    if sites:
                        # Take the first one found
                        potential_site = sites[0]
                    else:
                        potential_site = None
                else:
                    potential_site = None
            
            if potential_site and potential_site.exists():
                venv_site_packages = str(potential_site)

    # Apply the site-packages if found
    if venv_site_packages:
        site.addsitedir(venv_site_packages)
    
    # 4. Fail Fast: Verify critical dependencies
    # We check for pydantic as a baseline dependency for the project
    try:
        import pydantic # noqa: F401
    except ImportError:
        # Only raise if we think we found a venv but it's broken
        # or if we are clearly in an environment that should have it.
        raise RuntimeError(
            f"Blender Environment Bootstrap Failed.\n"
            f"Critical dependency 'pydantic' not found.\n"
            f"Detected site-packages: {venv_site_packages}\n"
            f"Please ensure the virtual environment is correctly set up."
        )

if __name__ == "__main__":
    setup_environment()
