import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from render_tag.orchestration.persistent_worker import PersistentWorkerProcess

@patch("subprocess.Popen")
@patch("render_tag.orchestration.zmq_client.ZmqHostClient")
@patch("render_tag.common.environment.get_venv_site_packages")
def test_persistent_worker_injects_env_vars(mock_get_venv, mock_zmq_client, mock_popen, tmp_path):
    # Setup mocks
    mock_get_venv.return_value = "/mock/venv/site-packages"
    mock_popen_instance = mock_popen.return_value
    mock_popen_instance.poll.return_value = None
    
    # Mock status response to avoid timeout
    mock_client_instance = mock_zmq_client.return_value
    mock_resp = MagicMock()
    mock_resp.status = "SUCCESS" # Using string as in some contexts it might not be enum
    # Actually it should be ResponseStatus.SUCCESS
    from render_tag.schema.hot_loop import ResponseStatus
    mock_resp.status = ResponseStatus.SUCCESS
    mock_client_instance.send_command.return_value = mock_resp

    blender_script = tmp_path / "src" / "render_tag" / "backend" / "zmq_server.py"
    blender_script.parent.mkdir(parents=True)
    blender_script.touch()
    
    worker = PersistentWorkerProcess(
        worker_id="test-worker",
        port=8000,
        blender_script=blender_script,
        use_blenderproc=True
    )
    
    # Run start
    try:
        worker.start()
    except Exception:
        # We might get some errors because of deeper mocks needed, 
        # but we only care about Popen call
        pass
        
    # Verify Popen was called with correct environment
    assert mock_popen.called
    args, kwargs = mock_popen.call_args
    env = kwargs.get("env")
    
    assert env is not None
    assert env.get("RENDER_TAG_VENV_SITE_PACKAGES") == "/mock/venv/site-packages"
    assert env.get("PYTHONNOUSERSITE") == "1"
    assert "PYTHONPATH" in env
