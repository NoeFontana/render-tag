from unittest.mock import patch

from render_tag.orchestration.persistent_worker import PersistentWorkerProcess


@patch("subprocess.Popen")
@patch("render_tag.orchestration.persistent_worker.ZmqHostClient")
@patch("render_tag.common.utils.get_venv_site_packages")
@patch("time.sleep", return_value=None)
def test_persistent_worker_injects_env_vars(
    mock_sleep, mock_get_venv, mock_zmq_client, mock_popen, tmp_path
):
    # Setup mocks
    mock_get_venv.return_value = "/mock/venv/site-packages"
    mock_popen_instance = mock_popen.return_value
    mock_popen_instance.poll.return_value = None

    # Ensure ZmqHostClient mock returns a SUCCESS response
    from render_tag.schema.hot_loop import Response, ResponseStatus

    mock_resp = Response(status=ResponseStatus.SUCCESS, request_id="test", message="OK")

    # Configure the instance that will be created
    mock_client_instance = mock_zmq_client.return_value
    mock_client_instance.send_command.return_value = mock_resp

    blender_script = tmp_path / "src" / "render_tag" / "backend" / "zmq_server.py"
    blender_script.parent.mkdir(parents=True)
    blender_script.touch()

    worker = PersistentWorkerProcess(
        worker_id="test-worker", port=8000, blender_script=blender_script, use_blenderproc=True
    )

    # Run start - it should return immediately now if mock works
    worker.start()

    # Verify Popen was called with correct environment
    assert mock_popen.called
    _, kwargs = mock_popen.call_args
    env = kwargs.get("env")

    assert env is not None
    assert env.get("RENDER_TAG_VENV_SITE_PACKAGES") == "/mock/venv/site-packages"
    assert env.get("PYTHONNOUSERSITE") == "1"
    assert "PYTHONPATH" in env
