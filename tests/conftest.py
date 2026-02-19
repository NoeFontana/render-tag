"""
Pytest configuration for render-tag.

This file sets up the test environment by injecting mocks for Blender modules
BEFORE any tests run or imports happen.
"""

import sys
from pathlib import Path

import pytest

# Add src to pythonpath so we can import modules under test
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# --- MOCK INJECTION START ---
# We must inject mocks BEFORE any test collection happens,
# because test files import modules that import blenderproc.

# Import our mocks
# Add root to sys.path to find 'tests'
sys.path.append(str(Path(__file__).parent.parent))
from render_tag.backend.mocks import (  # noqa: E402
    blender_api,
    blenderproc_api,
    mathutils_api,
)

# Inject them into sys.modules
sys.modules["bpy"] = blender_api
sys.modules["blenderproc"] = blenderproc_api
sys.modules["mathutils"] = mathutils_api
# --- MOCK INJECTION END ---


def pytest_configure(config):
    """Custom configuration for pytest."""
    # Redirect all temporary test data to output/test_results (gitignored)
    project_root = Path(__file__).parent.parent
    test_results_dir = project_root / "output" / "test_results"
    test_results_dir.mkdir(parents=True, exist_ok=True)
    
    # basetemp is the root for all tmp_path fixtures
    config.option.basetemp = str(test_results_dir)


@pytest.fixture(autouse=True)
def cleanup_orchestrators():
    """Ensure all orchestrators and workers are cleaned up after each test."""
    yield
    from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator
    UnifiedWorkerOrchestrator.cleanup_all()


@pytest.fixture(scope="session", autouse=True)
def stabilized_bridge():
    """
    Ensure BlenderBridge is stabilized for all tests.
    Autouse session fixture to avoid redundant stabilize() calls.
    """
    import numpy as np

    from render_tag.backend.bridge import bridge
    bridge.np = np
    bridge.stabilize()
    return bridge

@pytest.fixture
def port_generator():
    """
    Provides a unique, available port for each test.
    Helps avoid collisions in parallel execution.
    """
    import random
    import socket
    
    def _find_free_port():
        while True:
            port = random.randint(20000, 30000)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
    return _find_free_port

@pytest.fixture(scope="session")
def mock_blender_environment():
    """
    Fixture to ensure mocks are present (redundant but explicit).
    """
    # Already done at top level
    yield
