import blenderproc as bproc  # noqa: F401, I001

import sys
from pathlib import Path

# 1. Bootstrap sys.path to include 'src'
# resolving: scripts/worker_bootstrap.py -> project_root -> src
# This file is in scripts/, so parent is root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# 2. Delegate to the actual backend server
if __name__ == "__main__":
    try:
        from render_tag.backend.zmq_server import main

        main()
    except ImportError as e:
        import traceback

        print(f"CRITICAL: Failed to import backend server: {e}")
        print(f"sys.path: {sys.path}")
        traceback.print_exc()
        sys.exit(1)
