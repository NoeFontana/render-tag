import socket
from unittest.mock import patch

from render_tag.core.utils import is_port_in_use
from render_tag.orchestration.orchestrator import UnifiedWorkerOrchestrator


def test_is_port_in_use():
    port = 35005
    assert not is_port_in_use(port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        assert is_port_in_use(port)

    assert not is_port_in_use(port)


def test_orchestrator_port_collision_avoidance():
    with (
        patch("hashlib.md5") as mock_md5,
        patch("random.randint") as mock_randint,
        patch("random.random") as mock_random,
        patch("render_tag.orchestration.orchestrator.is_port_in_use") as mock_is_port_in_use,
    ):
        mock_md5.return_value.hexdigest.return_value = "0"
        mock_randint.return_value = 0
        mock_random.return_value = 0
        
        # Deterministically mock port availability to avoid CI flakiness
        # Return True if port is 26000 (simulating collision), False otherwise
        mock_is_port_in_use.side_effect = lambda port: port == 26000

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
            s1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s1.bind(("127.0.0.1", 26000))
            s1.listen(1)

            with UnifiedWorkerOrchestrator(num_workers=1, base_port=26000, mock=True) as orch:
                assert orch.running
                worker = orch.workers[0]
                assert worker.port == 26200
