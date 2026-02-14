import blenderproc as bproc  # isort: skip
import os
import sys

# TOP-LEVEL import for blenderproc to satisfy its strict runtime checks.
# This file is now a thin wrapper. All logic is in worker_server.py.
# We no longer need '# isort: skip' because this file has minimal imports.

if os.environ.get("RENDER_TAG_BACKEND_MOCK") == "1":

    class DummyBproc:
        def init(self):
            pass

        def clean_up(self):
            pass

    bproc = DummyBproc()

from pathlib import Path

# Bootstrap environment to ensure we can import our modules
try:
    from render_tag.backend import bootstrap

    bootstrap.setup_environment()
except ImportError:
    _src = os.environ.get("RENDER_TAG_SRC_ROOT")
    if not _src:
        _curr = Path(__file__).resolve().parent
        while _curr.parent != _curr:
            if (_curr / "render_tag").is_dir():
                _src = str(_curr.parent)
                break
            _curr = _curr.parent
    if _src:
        sys.path.insert(0, _src)
        from render_tag.backend import bootstrap

        bootstrap.setup_environment()

import logging

from render_tag.backend.worker_server import ZmqBackendServer

# Configure simple logging for the wrapper
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wrapper")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--mock", action="store_true")
    # Kept for compatibility, though bootstrap handles it
    parser.add_argument("--src-root", type=str, default=None)
    parser.add_argument("--max-renders", type=int, default=None)
    args, unknown = parser.parse_known_args()

    if args.src_root:
        # Also add repo root (parent of src) to allow importing 'tests'
        repo_root = str(Path(args.src_root).parent)
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

    logger.info(f"Wrapper initializing worker server on port {args.port}")
    try:
        bproc_mock, bpy_mock = None, None
        if os.environ.get("RENDER_TAG_BACKEND_MOCK") == "1":
            try:
                # Try to load robust mocks from tests if available
                from tests.mocks import blender_api as bpy_mock
                from tests.mocks import blenderproc_api as bproc_mock
            except ImportError as e:
                logger.warning(f"Failed to import robust mocks: {e}. Using minimal dummy.")
                # Fallback to the local dummy if tests not found
                bproc_mock = bproc  # The local DummyBproc instance

                # Minimal DummyBpy to prevent immediate crash if engine accesses it
                class DummyBpyStats:
                    def __getattr__(self, name):
                        return None

                class DummyBpy:
                    context = DummyBpyStats()
                    data = DummyBpyStats()

                bpy_mock = DummyBpy()

        server = ZmqBackendServer(port=args.port, bproc_mock=bproc_mock, bpy_mock=bpy_mock)
        server.run(max_renders=args.max_renders)
    except Exception as e:
        logger.exception(f"Wrapper crashed: {e}")
        sys.exit(1)
