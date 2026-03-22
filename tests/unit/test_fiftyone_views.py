from unittest.mock import MagicMock

import fiftyone as fo


def test_saved_views_creation():
    """
    Test that we create saved views for error tags and calibration boards.
    """
    from render_tag.viz.fiftyone_tool import create_saved_views

    mock_dataset = MagicMock(spec=fo.Dataset)
    mock_error_view = MagicMock()
    mock_cal_view = MagicMock()
    mock_cal_view.__len__ = MagicMock(return_value=0)

    mock_dataset.match_tags.return_value = mock_error_view
    mock_dataset.exists.return_value = mock_cal_view

    # ACT
    create_saved_views(mock_dataset)

    # VERIFY — Anomalies view
    mock_dataset.match_tags.assert_called()
    args = mock_dataset.match_tags.call_args[0]
    assert any(tag in args[0] for tag in ["ERR_OOB", "ERR_OVERLAP", "ERR_SCALE_DRIFT"])
    mock_dataset.save_view.assert_any_call("Anomalies", mock_error_view)


def test_saved_views_calibration_when_present():
    """
    Test that calibration view is created when calibration_points exist.
    """
    from render_tag.viz.fiftyone_tool import create_saved_views

    mock_dataset = MagicMock(spec=fo.Dataset)
    mock_error_view = MagicMock()
    mock_cal_view = MagicMock()
    mock_cal_view.__len__ = MagicMock(return_value=5)

    mock_dataset.match_tags.return_value = mock_error_view
    mock_dataset.exists.return_value = mock_cal_view

    create_saved_views(mock_dataset)

    mock_dataset.exists.assert_called_with("calibration_points")
    mock_dataset.save_view.assert_any_call("Calibration Boards", mock_cal_view)
