import polars as pl

from render_tag.data_io.auditor import OutlierExporter


def test_outlier_exporter_identifies_and_links(tmp_path):
    """Verify that OutlierExporter identifies outliers and creates symlinks."""
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    images_dir = dataset_dir / "images"
    images_dir.mkdir()
    
    # Create dummy images
    (images_dir / "img1.png").touch()
    (images_dir / "img2.png").touch()
    
    data = {
        "image_id": ["img1", "img2"],
        "distance": [-1.0, 5.0] # img1 is an outlier
    }
    df = pl.DataFrame(data)
    
    exporter = OutlierExporter(dataset_dir, df)
    outlier_dir = exporter.export()
    
    assert outlier_dir.exists()
    assert (outlier_dir / "img1.png").exists()
    assert not (outlier_dir / "img2.png").exists()
    # Check if it is a symlink
    assert (outlier_dir / "img1.png").is_symlink()
