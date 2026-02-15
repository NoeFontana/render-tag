"""
Worker Server Entry Point.
"""

import argparse
import os
from pathlib import Path

from render_tag.backend import bootstrap
from render_tag.backend.worker_server import ZmqBackendServer
from render_tag.core.logging import setup_logging
from render_tag.core.schema.job import JobSpec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--shard-id", type=str, default="0")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--max-renders", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--job-spec", type=Path, default=None)
    args, _ = parser.parse_known_args()

    # 1. Setup Environment
    bootstrap.setup_environment()
    setup_logging()

    # 2. Load Job Spec
    job_spec = None
    if args.job_spec and args.job_spec.exists():
        job_spec = JobSpec.from_file(args.job_spec)

    # 3. Handle Mocks
    mocks = {}
    if args.mock or os.environ.get("RENDER_TAG_BACKEND_MOCK") == "1":
        from render_tag.backend.mocks import (
            blender_api as bpy_mock,
            blenderproc_api as bproc_mock,
            mathutils_api as math_mock,
        )
        mocks = {"bproc_mock": bproc_mock, "bpy_mock": bpy_mock, "math_mock": math_mock}

    # 4. Start Server
    server = ZmqBackendServer(
        port=args.port,
        shard_id=args.shard_id,
        seed=job_spec.global_seed if job_spec else args.seed,
        job_spec=job_spec,
        **mocks,
    )
    server.run(max_renders=args.max_renders)


if __name__ == "__main__":
    main()
