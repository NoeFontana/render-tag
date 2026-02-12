"""
Advanced unit tests for data_io.visualization, focusing on parsing and data handling.
"""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from render_tag.data_io.visualization import visualize_dataset, visualize_recipe


def test_visualize_dataset_data_parsing(tmp_path: Path, capsys):
    # Setup dummy dataset
    img_dir = tmp_path / "images"
    img_dir.mkdir()

    # Create a dummy image
    img = Image.new("RGB", (640, 480), color="black")
    img.save(img_dir / "scene_0001.png")

    # Create tags.csv
    csv_path = tmp_path / "tags.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["image_id", "tag_id", "tag_family", "x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"]
        )
        writer.writerow(
            ["scene_0001", "42", "tag36h11", "100", "100", "200", "100", "200", "200", "100", "200"]
        )

    visualize_dataset(tmp_path, save_viz=True)

    # Check if visualization was saved
    viz_dir = tmp_path / "visualizations"
    assert (viz_dir / "scene_0001_viz.png").exists()

    # Check output
    captured = capsys.readouterr()
    assert "Saved visualization" in captured.out


@patch("render_tag.data_io.visualization.plt")
def test_visualize_recipe_complex(mock_plt, tmp_path: Path):
    mock_plt.subplots.return_value = (MagicMock(), MagicMock())
    # Create a recipe with multiple objects and cameras
    recipe = {
        "scene_id": 1,
        "objects": [
            {
                "name": "board",
                "type": "BOARD",
                "location": [0, 0, 0],
                "rotation_euler": [0, 0, 0],
                "scale": [1, 1, 1],
                "properties": {},
            },
            {
                "name": "tag1",
                "type": "TAG",
                "location": [0.1, 0.1, 0],
                "rotation_euler": [0, 0, 0.5],
                "scale": [1, 1, 1],
                "properties": {"tag_id": 10},
            },
        ],
        "cameras": [
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 5], [0, 0, 0, 1]],
                "scene_id": 1,
                "intrinsics": {"fov": 60.0, "resolution": [640, 480]},
            }
        ],
    }

    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(json.dumps([recipe]))

    visualize_recipe(recipe_path, tmp_path)

    # Verify that plot functions were called
    assert mock_plt.savefig.called
    assert mock_plt.close.called
