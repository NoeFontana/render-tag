import json
from unittest.mock import MagicMock, patch

import pytest

from render_tag.data_io.visualization import visualize_dataset


@pytest.fixture
def mock_dataset(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    # Create a dummy image
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="white")
    img.save(images_dir / "1.png")

    # Create COCO annotations
    coco = {
        "images": [{"id": 1, "file_name": "1.png", "width": 100, "height": 100}],
        "annotations": [
            {
                "image_id": 1,
                "category_id": 1,
                "bbox": [10, 10, 20, 20],
                "keypoints": [10, 10, 2, 30, 10, 2, 30, 30, 2, 10, 30, 2],
                "num_keypoints": 4,
            }
        ],
        "categories": [{"id": 1, "name": "tag", "keypoints": ["bl", "br", "tr", "tl"]}],
    }

    (tmp_path / "annotations.json").write_text(json.dumps(coco))
    return tmp_path


def test_visualize_dataset_coco(mock_dataset):
    with patch("render_tag.data_io.visualization.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        mock_img.convert.return_value = mock_img

        # We also need to mock ImageDraw because we can't draw on a mock image easily
        with patch("render_tag.data_io.visualization.ImageDraw.Draw") as mock_draw:
            draw_instance = MagicMock()
            mock_draw.return_value = draw_instance

            visualize_dataset(mock_dataset, save_viz=False)

            # Check if line/ellipse drawing was called
            # Since we have keypoints, we expect 4 lines (edges)
            # + 8 lines (4 corners * 2 crosshairs) = 12 lines
            # Previous assert: draw_instance.line.call_count >= 4
            # We removed ellipse drawing.
            assert draw_instance.line.call_count >= 12
            # assert draw_instance.ellipse.call_count >= 4 # Removed
