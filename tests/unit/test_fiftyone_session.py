import pytest
from unittest.mock import MagicMock, patch
import fiftyone as fo

def test_session_reuse_detection():
    """
    Test that we can detect if a FiftyOne session is already running.
    """
    from render_tag.viz.fiftyone_tool import find_active_session
    
    with patch("fiftyone.core.session.Session") as mock_session_cls:
        # Mock no active sessions
        mock_session_cls._instances = {}
        assert find_active_session() is None
        
        # Mock active session
        mock_active = MagicMock()
        mock_session_cls._instances = {id(mock_active): mock_active}
        assert find_active_session() == mock_active
