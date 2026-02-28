from unittest.mock import MagicMock, call, patch

import zmq

from render_tag.core.schema.hot_loop import CommandType
from render_tag.orchestration.client import ZmqHostClient


def test_send_command_sets_send_timeout():
    """
    Verify that send_command sets BOTH RCVTIMEO and SNDTIMEO 
    when a custom timeout_ms is provided.
    """
    with patch("zmq.Context") as mock_ctx_cls:
        mock_ctx = mock_ctx_cls.return_value
        mock_socket = MagicMock()
        mock_ctx.socket.return_value = mock_socket
        
        # Configure successful response
        from render_tag.core.schema.hot_loop import Response, ResponseStatus
        valid_response = Response(status=ResponseStatus.SUCCESS, request_id="test", message="ok").model_dump_json()
        mock_socket.recv_string.return_value = valid_response
        mock_socket.poll.return_value = True
        
        # Initialize client with default timeout of 300000ms
        client = ZmqHostClient(port=5555, context=mock_ctx, timeout_ms=300000)
        
        # Call send_command with a short timeout (e.g., shutdown scenario)
        short_timeout = 500
        client.send_command(CommandType.STATUS, timeout_ms=short_timeout)
        
        # Verify setsockopt calls
        # We expect RCVTIMEO and SNDTIMEO to be set to 500 before send
        calls = [
            call(zmq.RCVTIMEO, short_timeout),
            call(zmq.SNDTIMEO, short_timeout)
        ]
        mock_socket.setsockopt.assert_has_calls(calls, any_order=True)
        
        # Verify that they are reset to default (300000) in finally block
        reset_calls = [
            call(zmq.RCVTIMEO, 300000),
            call(zmq.SNDTIMEO, 300000)
        ]
        mock_socket.setsockopt.assert_has_calls(reset_calls, any_order=True)

def test_send_command_defaults():
    """Verify standard behavior uses default timeout."""
    with patch("zmq.Context") as mock_ctx_cls:
        mock_ctx = mock_ctx_cls.return_value
        mock_socket = MagicMock()
        mock_ctx.socket.return_value = mock_socket
        
        # Configure successful response
        from render_tag.core.schema.hot_loop import Response, ResponseStatus
        valid_response = Response(status=ResponseStatus.SUCCESS, request_id="test", message="ok").model_dump_json()
        mock_socket.recv_string.return_value = valid_response
        mock_socket.poll.return_value = True
        
        default_timeout = 10000
        client = ZmqHostClient(port=5555, context=mock_ctx, timeout_ms=default_timeout)
        
        client.send_command(CommandType.STATUS)
        
        # Should just set to default (or technically could skip setting if logic optimized, 
        # but current impl sets it ensuring consistency)
        calls = [
            call(zmq.RCVTIMEO, default_timeout),
            call(zmq.SNDTIMEO, default_timeout)
        ]
        mock_socket.setsockopt.assert_has_calls(calls, any_order=True)
