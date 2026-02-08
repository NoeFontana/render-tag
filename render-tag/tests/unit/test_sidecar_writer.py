import json

from render_tag.data_io.writers import SidecarWriter
from render_tag.schema import SceneProvenance


def test_sidecar_writer(tmp_path):
    prov = SceneProvenance(
        git_hash="123",
        timestamp="now",
        recipe_snapshot={"a": 1}
    )
    # Output path is usually the dataset root
    writer = SidecarWriter(tmp_path)
    
    # We pass the image base name (without extension)
    path = writer.write_sidecar("scene_0000", prov)
    
    assert path.exists()
    assert path.name == "scene_0000_meta.json"
    assert path.parent == tmp_path / "images" # Assuming writer handles structure? Or just flat.
    
    # Actually, writers usually take the output directory.
    # If I pass output_dir=tmp_path, writer typically writes to output_dir/images if it's
    # image meta?
    # Or just alongside the image.
    
    # Let's assume write_sidecar takes just the name, and writes to tmp_path (flat) or configured
    # structure. Existing writers like CSVWriter take full path.
    # COCOWriter takes output_dir.
    
    # Let's say SidecarWriter takes output_dir.
    # And write_sidecar writes to output_dir/images/NAME_meta.json (if images go there).
    # Or output_dir/NAME_meta.json.
    
    # I'll assert path location after implementation. For now, check content.
    with open(path) as f:
        data = json.load(f)
        assert data["git_hash"] == "123"
        assert data["recipe_snapshot"]["a"] == 1
