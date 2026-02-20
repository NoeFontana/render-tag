import threading
import time

import pytest

from render_tag.core.errors import WorkerCommunicationError
from render_tag.core.schema.hot_loop import CommandType, ResponseStatus
from render_tag.orchestration import ZmqHostClient


def mock_zmq_server(port, delay=0):
    import json

    import zmq

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)
    socket.bind(f"tcp://127.0.0.1:{port}")

    try:
        # Wait for a message
        if socket.poll(2000):
            socket.recv_string()
            if delay > 0:
                time.sleep(delay)

            resp = {
                "status": "SUCCESS",
                "message": "Mock response",
                "request_id": "mock-id",
                "data": {},
            }
            socket.send_string(json.dumps(resp))
    finally:
        socket.close()
        context.term()


def test_zmq_client_success():
    port = 5556
    server_thread = threading.Thread(target=mock_zmq_server, args=(port,))
    server_thread.start()

    time.sleep(0.1)  # Wait for bind

    with ZmqHostClient(port=port) as client:
        resp = client.send_command(CommandType.STATUS)
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.message == "Mock response"


def test_zmq_client_timeout():
    port = 5557
    # Start server with delay significantly longer than client timeout
    # Staff Engineer: Increase delay to avoid race conditions
    server_thread = threading.Thread(target=mock_zmq_server, args=(port, 2.0))
    server_thread.start()

    time.sleep(0.1)

    # Set small timeout
    with (
        ZmqHostClient(port=port, timeout_ms=200) as client,
        pytest.raises(WorkerCommunicationError, match=r"TIMEOUT sending STATUS"),
    ):
        client.send_command(CommandType.STATUS)
