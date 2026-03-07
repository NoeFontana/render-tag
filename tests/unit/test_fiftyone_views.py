import pytest
from unittest.mock import MagicMock, patch
import fiftyone as fo

def test_error_view_creation():
    """
    Test that we can create a saved view for error tags.
    """
    from render_tag.viz.fiftyone_tool import create_error_view
    
    mock_dataset = MagicMock(spec=fo.Dataset)
    mock_view = MagicMock()
    mock_dataset.match_tags.return_value = mock_view
    
    # ACT
    create_error_view(mock_dataset)
    
    # VERIFY
    mock_dataset.match_tags.assert_called()
    args = mock_dataset.match_tags.call_args[0]
    # Should check for our error tags
    assert any(tag in args[0] for tag in ["ERR_OOB", "ERR_OVERLAP", "ERR_SCALE_DRIFT"])
    
    # Check that it's saved
    mock_dataset.save_view.assert_called_with("Anomalies", mock_view)
