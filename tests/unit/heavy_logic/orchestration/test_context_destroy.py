import zmq
import pytest
from unittest.mock import MagicMock, patch
from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator, OrchestratorConfig

@pytest.mark.timeout(2)
def test_orchestrator_forces_context_destroy():
    """
    Verify that Orchestrator.stop() uses context.destroy(linger=0) 
    to clean up even if sockets are left open (leaked).
    """
    # 1. Setup a real ZMQ context
    real_context = zmq.Context()
    
    # 2. Create a "leaked" socket on this context
    # If we used context.term(), this would hang forever because the socket is open.
    # With context.destroy(linger=0), it should close the socket and terminate immediately.
    leaked_socket = real_context.socket(zmq.REP)
    leaked_socket.bind("tcp://127.0.0.1:0") # Bind to random port
    
    # 3. Inject this context into an Orchestrator
    config = OrchestratorConfig(num_workers=1, mock=True)
    orchestrator = UnifiedWorkerOrchestrator(config=config)
    orchestrator.context = real_context
    orchestrator.running = True
    
    # 4. Call stop()
    # This should NOT hang.
    orchestrator.stop()
    
    # 5. Verify context is terminated
    assert list(real_context._sockets) == [] # Should be empty? or context closed
    assert real_context.closed
    
    # Verify the leaked socket is also closed (invalid)
    assert leaked_socket.closed

if __name__ == "__main__":
    test_orchestrator_forces_context_destroy()
