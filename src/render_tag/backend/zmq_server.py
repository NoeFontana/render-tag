import blenderproc as bproc  # noqa: F401, I001

import os
import sys
from pathlib import Path

# Verify and setup environment via the centralized bootstrap
try:
    from render_tag.backend import bootstrap

    bootstrap.setup_environment()
except ImportError:
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
from render_tag.core.logging import get_logger, setup_logging


def main():
    import argparse

    from render_tag.core.schema.job import JobSpec
    from render_tag.generation.scene import Generator

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--shard-id", type=str, default="0")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--max-renders", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)  # Fallback if no job-spec
    parser.add_argument("--job-spec", type=Path, default=None)

    args, _unknown = parser.parse_known_args()

    # Setup structured logging
    setup_logging()

    # Retrieve job_id from environment
    job_id = os.environ.get("RENDER_TAG_JOB_ID", "local")

    # Create context-bound logger
    logger = get_logger("zmq_server").bind(job_id=job_id, worker_id=args.shard_id, mock=args.mock)

    logger.info(f"Starting ZmqBackendServer on port {args.port}", extra={"seed": args.seed})

    # Global Exception Hook for Crash Reporting
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
            event="worker_crash",
        )

    sys.excepthook = handle_exception

    try:
        math_mock = None
        if args.mock or os.environ.get("RENDER_TAG_BACKEND_MOCK") == "1":
            try:
                from render_tag.backend.mocks import blender_api as bpy_mock
                from render_tag.backend.mocks import blenderproc_api as bproc_mock
                from render_tag.backend.mocks import mathutils_api as math_mock
            except ImportError as e:
                logger.error(f"Failed to load production mocks: {e}")
                sys.exit(1)

        # Load Job Spec if provided
        job_spec = None
        if args.job_spec:
            try:
                with open(args.job_spec) as f:
                    job_spec = JobSpec.model_validate_json(f.read())
                logger.info(f"Loaded Job Spec: {job_spec.job_id}")
            except Exception as e:
                logger.error(f"Failed to load job spec: {e}")
                sys.exit(1)

        server = ZmqBackendServer(
            port=args.port,
            shard_id=args.shard_id,
            bproc_mock=bproc_mock,
            bpy_mock=bpy_mock,
            math_mock=math_mock,
            seed=args.seed if job_spec is None else job_spec.global_seed,
            logger=logger,  # Inject bound logger
            job_spec=job_spec,
        )
        server.run(max_renders=args.max_renders)
    except Exception as e:
        logger.exception(f"ZMQ Server failed to start: {e}", event="startup_failure")
        sys.exit(1)


if __name__ == "__main__":
    main()
