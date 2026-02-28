from unittest.mock import MagicMock, patch

from render_tag.orchestration.client import ZmqHostClient
from render_tag.orchestration.orchestrator import OrchestratorConfig, UnifiedWorkerOrchestrator


def test_zmq_client_disconnect_linger():
    """Verify that ZmqHostClient.disconnect sets linger=0 on sockets."""
    with patch("zmq.Context") as mock_ctx_cls:
        mock_ctx = mock_ctx_cls.return_value
        mock_task_sock = MagicMock()
        mock_mgmt_sock = MagicMock()
        
        mock_ctx.socket.side_effect = [mock_task_sock, mock_mgmt_sock]
        
        client = ZmqHostClient(port=5555, context=mock_ctx)
        
        # Verify initial setup
        assert client.task_socket == mock_task_sock
        assert client.mgmt_socket == mock_mgmt_sock
        
        # Disconnect should close sockets with linger=0
        client.disconnect()
        
        mock_task_sock.close.assert_called_with(linger=0)
        mock_mgmt_sock.close.assert_called_with(linger=0)
        assert client.task_socket is None
        assert client.mgmt_socket is None

def test_orchestrator_stop_sequence():
    """Verify the sequence of Orchestrator.stop() and resource cleanup."""
    with patch("render_tag.orchestration.orchestrator.PersistentWorkerProcess") as mock_worker_cls:
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker
        
        config = OrchestratorConfig(num_workers=1, mock=True)
        orchestrator = UnifiedWorkerOrchestrator(config=config)
        
        orchestrator.start()
        assert orchestrator.running
        
        # Stop should call worker.stop() via ResourceStack
        orchestrator.stop()
        
        assert not orchestrator.running
        mock_worker.stop.assert_called()

def test_worker_server_finalize_outside_lock():
    """
    Staff Engineer: Verify that _finalize_writers is called after 
    reaching max renders and outside the lock.
    """
    from render_tag.backend.worker_server import ZmqBackendServer
    from render_tag.core.schema.hot_loop import Command, CommandType, ResponseStatus
    
    with patch("render_tag.backend.worker_server.bridge"), \
         patch("render_tag.backend.worker_server.zmq.Context"), \
         patch("threading.Thread"):
        
        server = ZmqBackendServer(port=5555)
        mock_writer = MagicMock()
        server.writers = {"mock": mock_writer}
        server.running = True
        
        # We need to mock the socket and its poll/recv behavior
        server.task_socket = MagicMock()
        # Return True once for RENDER, then False to test loop behavior
        # But we need to make sure the loop exits.
        # run() loop exits if self.running is False.
        # self.running becomes False if at_limit is True.
        server.task_socket.poll.return_value = True
        
        cmd = Command(command_type=CommandType.RENDER, request_id="1")
        server.task_socket.recv_string.return_value = cmd.model_dump_json()
        
        # Mock _handle_command to simulate a successful render AND increment renders_completed
        def mock_handle_side_effect(c):
            server.renders_completed += 1
            return MagicMock(status=ResponseStatus.SUCCESS)
        
        server._handle_command = MagicMock(side_effect=mock_handle_side_effect)
        
        # Set renders_completed to 0
        server.renders_completed = 0
        
        # Run loop for 1 iteration with max_renders=1
        with patch.object(server, "_check_memory", return_value=True):
            # server.run will set running=False after the first render because at_limit will be True
            server.run(max_renders=1)
            
        # Verify writers were finalized
        mock_writer.save.assert_called_once()
        assert server.renders_completed == 1
        assert not server.running
