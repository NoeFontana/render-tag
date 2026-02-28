"""
Pytest configuration for render-tag.

This file sets up the test environment by injecting mocks for Blender modules
BEFORE any tests run or imports happen. It also provides fixtures for
orchestration cleanup and bridge stabilization.
"""

from __future__ import annotations

import os
import socket
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.main import Session
    from _pytest.nodes import Item

# --- PATH & MOCK INJECTION ---
# We must inject mocks BEFORE any test collection happens, because many
# modules under test import bpy or blenderproc at the module level.

# 1. Resolve project structure
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"

# 2. Add src and root to sys.path
# 'src' for the modules under test, 'root' for potential test-to-test imports
for path in [SRC_PATH, PROJECT_ROOT]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

def _inject_blender_mocks() -> None:
    """Inject our custom mocks into sys.modules to satisfy Blender dependencies."""
    try:
        # Import the mock modules from the codebase
        from render_tag.backend.mocks import (
            blender_api,
            blenderproc_api,
            mathutils_api,
        )

        # Map them to the names expected by external libraries
        sys.modules["bpy"] = blender_api
        sys.modules["blenderproc"] = blenderproc_api
        sys.modules["mathutils"] = mathutils_api
    except ImportError as e:
        # Fallback for edge cases where src/ is not yet fully available
        print(f"Warning: Failed to inject Blender mocks: {e}", file=sys.stderr)

# Execute immediately during conftest collection
_inject_blender_mocks()


def pytest_configure(config: Config) -> None:
    """
    Custom configuration for pytest.
    
    Ensures test outputs are localized to output/test_results and handles
    worker isolation for pytest-xdist.
    """
    test_results_dir = PROJECT_ROOT / "output" / "test_results"
    test_results_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure basetemp for all tmp_path fixtures.
    # In xdist, workers must have unique temp directories.
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id is not None:
        config.option.basetemp = str(test_results_dir / worker_id)
    else:
        config.option.basetemp = str(test_results_dir)


def pytest_collection_modifyitems(session: Session, config: Config, items: list[Item]) -> None:
    """
    Modify collected test items.
    
    Groups integration tests using the xdist_group marker to ensure they run
    on a single worker (serially), preventing memory exhaustion from multiple
    Blender/Subprocess instances.
    """
    for item in items:
        # Group integration tests by location or marker
        is_integration = "integration" in str(item.fspath) or item.get_closest_marker("integration")
        if is_integration:
            item.add_marker(pytest.mark.xdist_group(name="serial_integration"))


@pytest.fixture(autouse=True)
def cleanup_orchestrators() -> Generator[None, None, None]:
    """Ensure all orchestrators and workers are cleaned up after each test."""
    yield
    # Late import to prevent circular dependency issues during collection
    from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator
    UnifiedWorkerOrchestrator.cleanup_all()


@pytest.fixture(scope="session", autouse=True)
def stabilized_bridge() -> Any:
    """
    Ensure BlenderBridge is stabilized for all tests.
    
    Autouse session fixture to avoid redundant stabilize() calls across tests.
    """
    import numpy as np

    from render_tag.backend.bridge import bridge
    
    bridge.np = np
    bridge.stabilize()
    return bridge


@pytest.fixture
def port_generator() -> Callable[[], int]:
    """
    Provides a factory for finding available ephemeral ports.
    
    Used to prevent port collisions when tests spin up independent ZMQ workers.
    """
    def _find_free_port() -> int:
        """Find an available port using the OS ephemeral port range."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return int(s.getsockname()[1])
            
    return _find_free_port


@pytest.fixture(scope="session")
def mock_blender_environment() -> None:
    """
    Fixture ensuring Blender mocks are active (redundant but explicit).
    """
    # Injection handled at module level, this fixture is for explicit test dependency.
    pass
