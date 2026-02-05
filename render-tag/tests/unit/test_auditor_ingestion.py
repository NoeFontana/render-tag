import json
import pytest
import polars as pl
from pathlib import Path
from render_tag.data_io.auditor import DatasetReader

@pytest.fixture
def dummy_dataset(tmp_path):
    """Creates a dummy dataset for testing ingestion."""
    dataset_dir = tmp_path / "dataset_v1"
    dataset_dir.mkdir()
    
    # Create tags.csv
    tags_path = dataset_dir / "tags.csv"
    tags_content = [
        ["image_id", "tag_id", "tag_family", "x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"],
        ["scene_0000_cam_0000", "0", "apriltag_36h11", "100", "100", "200", "100", "200", "200", "100", "200"],
        ["scene_0000_cam_0000", "1", "apriltag_36h11", "300", "300", "400", "300", "400", "400", "300", "400"],
        ["scene_0001_cam_0000", "0", "apriltag_36h11", "150", "150", "250", "150", "250", "250", "150", "250"],
    ]
    import csv
    with open(tags_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(tags_content)
        
    # Create manifest.json
    manifest_path = dataset_dir / "manifest.json"
    manifest_data = {
        "experiment_name": "test_exp",
        "variant_id": "v000",
        "config": {"dataset": {"name": "test"}}
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)
        
    # Create sidecar metadata
    images_dir = dataset_dir / "images"
    images_dir.mkdir()
    
    meta_0 = images_dir / "scene_0000_cam_0000_meta.json"
    with open(meta_0, "w") as f:
        json.dump({
            "recipe_snapshot": {
                "world": {"lighting": {"intensity": 100.0}}
            }
        }, f)
        
    meta_1 = images_dir / "scene_0001_cam_0000_meta.json"
    with open(meta_1, "w") as f:
        json.dump({
            "recipe_snapshot": {
                "world": {"lighting": {"intensity": 50.0}}
            }
        }, f)
        
    return dataset_dir

def test_dataset_reader_loads_csv(dummy_dataset):
    """Verify that DatasetReader can load tags.csv into a Polars DataFrame."""
    reader = DatasetReader(dummy_dataset)
    df = reader.load_detections()
    
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 3
    assert "image_id" in df.columns
    assert "tag_id" in df.columns

def test_dataset_reader_joins_metadata(dummy_dataset):
    """Verify that DatasetReader can join sidecar metadata."""
    reader = DatasetReader(dummy_dataset)
    df = reader.load_full_dataset()
    
    assert "lighting_intensity" in df.columns
    # Check that lighting intensity matches for each row
    scene_0 = df.filter(pl.col("image_id") == "scene_0000_cam_0000")
    assert scene_0["lighting_intensity"][0] == 100.0
    
    scene_1 = df.filter(pl.col("image_id") == "scene_0001_cam_0000")
    assert scene_1["lighting_intensity"][0] == 50.0
