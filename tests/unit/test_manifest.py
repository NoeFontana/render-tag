import hashlib

from render_tag.common.manifest import DatasetManifest


def test_manifest_creation_and_hashing(tmp_path):
    # 1. Create dummy output files
    (tmp_path / "images").mkdir()
    img1 = tmp_path / "images" / "0001.png"
    img1.write_text("img1 content")

    csv_file = tmp_path / "tags.csv"
    csv_file.write_text("csv content")

    # 2. Create manifest
    manifest = DatasetManifest(job_id="test_job_123", output_dir=tmp_path)

    # 3. Hash files
    manifest.add_file(img1)
    manifest.add_file(csv_file)

    # 4. Save manifest
    manifest_path = manifest.save()

    assert manifest_path.exists()

    # 5. Verify content
    import json

    with open(manifest_path) as f:
        data = json.load(f)

    assert data["job_id"] == "test_job_123"
    assert "images/0001.png" in data["files"]
    assert data["files"]["tags.csv"] == hashlib.sha256(b"csv content").hexdigest()
