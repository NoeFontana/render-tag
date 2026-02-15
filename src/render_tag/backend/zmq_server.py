import os
import sys
import threading
from pathlib import Path

# Verify and setup environment via the centralized bootstrap
try:
    from render_tag.backend import bootstrap

    bootstrap.setup_environment()
except ImportError:
    # If bootstrap fails, we might be in an environment where PYTHONPATH isn't set yet.
    # We attempt a minimal discovery to find ourselves.
    _curr = Path(__file__).resolve().parent
    while _curr.parent != _curr:
        if (_curr / "render_tag").is_dir():
            sys.path.insert(0, str(_curr))
            break
        _curr = _curr.parent

    from render_tag.backend import bootstrap

    bootstrap.setup_environment()

import logging

from render_tag.backend.worker_server import ZmqBackendServer


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--max-renders", type=int, default=None)
    args, _unknown = parser.parse_known_args()

    # Configure basic fallback logging if bootstrap didn't setup JSON logging
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger("zmq_server")
    logger.info(f"Starting ZmqBackendServer on port {args.port} (mock={args.mock})")

    # --- ORPHAN PROTECTION (Stability Pattern) ---
    original_parent_pid = os.getppid()

    def monitor_parent_process():
        """Monitor the parent process and self-destruct if orphaned."""
        import signal
        import time

        while True:
            time.sleep(60)
            try:
                # If parent PID changed, the orchestrator died and we were re-parented
                if os.getppid() != original_parent_pid:
                    logger.error("Orchestrator (parent) died. Self-destructing to free resources.")
                    os.kill(os.getpid(), signal.SIGKILL)
            except Exception:
                pass

    parent_monitor_thread = threading.Thread(target=monitor_parent_process, daemon=True)
    parent_monitor_thread.start()

    try:
        bproc_mock, bpy_mock = None, None
        if args.mock or os.environ.get("RENDER_TAG_BACKEND_MOCK") == "1":
            try:
                from render_tag.backend.mocks import blender_api as bpy_mock
                from render_tag.backend.mocks import blenderproc_api as bproc_mock
            except ImportError as e:
                logger.error(f"Failed to load production mocks: {e}")
                sys.exit(1)

        server = ZmqBackendServer(port=args.port, bproc_mock=bproc_mock, bpy_mock=bpy_mock)
        server.run(max_renders=args.max_renders)
    except Exception as e:
        logger.exception(f"ZMQ Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
