"""
Pytest configuration for render-tag.

The ``pytest_plugins`` declaration loads the blender_mocks plugin before
collection begins; see ``tests/_plugins/blender_mocks/plugin.py`` for the
mock-injection invariant. This file keeps only fixtures and hooks that
genuinely belong to the root conftest.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config

pytest_plugins = ["tests._plugins.blender_mocks.plugin"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def pytest_configure(config: Config) -> None:
    """Ensure test outputs are localized and xdist workers have unique basetemp."""
    test_results_dir = PROJECT_ROOT / "output" / "test_results"
    test_results_dir.mkdir(parents=True, exist_ok=True)

    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id is not None:
        config.option.basetemp = str(test_results_dir / worker_id)
    else:
        config.option.basetemp = str(test_results_dir)


@pytest.fixture(autouse=True)
def cleanup_orchestrators() -> Generator[None, None, None]:
    """Tear down any orchestrators / workers spun up during a test."""
    yield
    from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator

    UnifiedWorkerOrchestrator.cleanup_all()


@pytest.fixture(scope="session", autouse=True)
def stabilized_bridge() -> Any:
    """Stabilize the BlenderBridge once per session."""
    import numpy as np

    from render_tag.backend.bridge import bridge

    bridge.np = np
    bridge.stabilize()
    return bridge


@pytest.fixture
def port_generator() -> Callable[[], int]:
    """Factory returning free ephemeral ports for tests that spin up ZMQ workers."""

    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return int(s.getsockname()[1])

    return _find_free_port
