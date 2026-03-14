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
    """Verify that the orchestrator avoids ports already in use."""
    import os as real_os

    original_urandom = real_os.urandom

    def controlled_urandom(n):
        """Return zeros for the port jitter calls (2 and 8 bytes), pass through for uuid."""
        if n in (2, 8):
            return b"\x00" * n
        return original_urandom(n)

    with (
        patch("hashlib.md5") as mock_md5,
        patch("render_tag.orchestration.orchestrator.os.urandom", side_effect=controlled_urandom),
        patch("render_tag.orchestration.orchestrator.is_port_in_use") as mock_is_port_in_use,
    ):
        mock_md5.return_value.hexdigest.return_value = "0"

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
                # With zeroed urandom, port_offset=0, jitter=0, so base=26000.
                # Port 26000 is in use, so it shifts by 200 to 26200.
                assert worker.port == 26200
