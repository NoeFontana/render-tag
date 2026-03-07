from pathlib import Path
from unittest.mock import patch


def test_rich_truth_indexing():
    """Test that rich_truth.json is indexed correctly by image_id and tag_id."""
    from render_tag.viz.fiftyone_tool import index_rich_truth

    # Mock rich truth data
    rich_truth_data = [
        {"image_id": "img1", "tag_id": 42, "distance": 5.0},
        {"image_id": "img1", "tag_id": 99, "distance": 2.0},
        {"image_id": "img2", "tag_id": 42, "distance": 10.0},
    ]

    # ACT
    index = index_rich_truth(rich_truth_data)

    # VERIFY
    assert index[("img1", 42)]["distance"] == 5.0
    assert index[("img1", 99)]["distance"] == 2.0
    assert index[("img2", 42)]["distance"] == 10.0
    assert len(index) == 3


@patch("fiftyone.dataset_exists", return_value=False)
@patch("fiftyone.delete_dataset")
@patch("fiftyone.Dataset.from_dir")
def test_coco_ingestion(mock_from_dir, mock_delete, mock_exists):
    """Test that FiftyOne COCO importer is called with correct paths."""
    from render_tag.viz.fiftyone_tool import load_dataset_from_coco

    dataset_path = Path("fake/dataset")

    # ACT
    load_dataset_from_coco(dataset_path, "test_ds")

    # VERIFY
    mock_from_dir.assert_called_once()
    _, kwargs = mock_from_dir.call_args
    assert kwargs["dataset_dir"] == str(dataset_path)
    assert kwargs["dataset_type"] is not None  # Should be fo.types.COCODetectionDataset
