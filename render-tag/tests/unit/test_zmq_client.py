import json
import threading
import time

import zmq

from render_tag.orchestration.zmq_client import ZmqHostClient
from render_tag.schema.hot_loop import CommandType, Response, ResponseStatus


def mock_zmq_server(port, response_delay=0):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{port}")

    try:
        # Wait for one command
        message = socket.recv_string()
        if response_delay > 0:
            time.sleep(response_delay)

        cmd_data = json.loads(message)
        resp = Response(
            status=ResponseStatus.SUCCESS,
            request_id=cmd_data["request_id"],
            message=f"Echo: {cmd_data['command_type']}",
        )
        socket.send_string(resp.model_dump_json())
    finally:
        socket.close()
        context.term()


def test_zmq_client_success():
    port = 5556
    server_thread = threading.Thread(target=mock_zmq_server, args=(port,))
    server_thread.start()

    time.sleep(0.1)  # Give server time to bind

    with ZmqHostClient(port=port) as client:
        resp = client.send_command(CommandType.STATUS)
        assert resp.status == ResponseStatus.SUCCESS
        assert "Echo: STATUS" in resp.message

    server_thread.join()


def test_zmq_client_timeout():
    port = 5557
    # Start server with delay longer than client timeout
    server_thread = threading.Thread(target=mock_zmq_server, args=(port, 0.5))
    server_thread.start()

    time.sleep(0.1)

    # Set small timeout
    with ZmqHostClient(port=port, timeout_ms=100) as client:
        resp = client.send_command(CommandType.STATUS)
        assert resp.status == ResponseStatus.FAILURE
        assert "Timeout" in resp.message

    server_thread.join()
