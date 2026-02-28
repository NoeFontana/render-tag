from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from render_tag.core.schema.hot_loop import CommandType, ResponseStatus
from render_tag.orchestration import PersistentWorkerProcess


def test_persistent_worker_lifecycle(tmp_path):
    """
    Staff Engineer: Test the PersistentWorkerProcess lifecycle using mocks
    to avoid subprocess/ZMQ overhead in unit tests.
    """
    with (
        patch("subprocess.Popen") as mock_popen,
        patch("render_tag.orchestration.worker.ZmqHostClient") as mock_client_cls,
    ):
        mock_process = MagicMock()
        mock_process.pid = 1234  # Real PID for safety check
        mock_process.poll.return_value = None  # Healthy
        mock_popen.return_value = mock_process

        mock_client = mock_client_cls.return_value
        mock_client.send_command.return_value = MagicMock(status=ResponseStatus.SUCCESS)

        worker = PersistentWorkerProcess(
            worker_id="test-1",
            port=5559,
            blender_script=tmp_path / "stub.py",
            blender_executable="python",
            startup_timeout=5,
            use_blenderproc=False,
        )

        worker.start()
        assert worker.is_healthy()
        assert mock_popen.called

        resp = worker.send_command(CommandType.STATUS)
        assert resp.status == ResponseStatus.SUCCESS
        assert mock_client.send_command.called

        with patch("os.killpg") as mock_killpg:
            worker.stop()
            assert not worker.is_healthy()
            assert mock_killpg.called
            assert mock_killpg.call_args[0][0] == 1234


def test_persistent_worker_failure():
    # Invalid executable will cause immediate failure
    worker = PersistentWorkerProcess(
        worker_id="fail-1",
        port=5560,
        blender_script=Path("non_existent.py"),
        blender_executable="/bin/non_existent_executable_12345",
        startup_timeout=5,
        use_blenderproc=False,
    )

    with pytest.raises((RuntimeError, OSError)):
        worker.start()
