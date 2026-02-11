from unittest.mock import patch

from render_tag.common.git import get_git_hash


def test_get_git_hash_returns_string():
    # Assuming we are in a git repo (we are)
    h = get_git_hash()
    assert isinstance(h, str)
    assert len(h) >= 7


def test_get_git_hash_fallback():
    with patch("subprocess.check_output") as mock_run:
        mock_run.side_effect = Exception("No git")
        h = get_git_hash()
        assert h == "unknown"
