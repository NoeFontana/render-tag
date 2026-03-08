import json

from render_tag.core.schema.base import SceneProvenance
from render_tag.data_io.writers import ProvenanceWriter


def test_provenance_writer(tmp_path):
    prov = SceneProvenance(git_hash="123", timestamp="now", recipe_snapshot={"a": 1})
    output_path = tmp_path / "provenance.json"
    writer = ProvenanceWriter(output_path)

    writer.add_provenance("scene_0000", prov)
    path = writer.save()

    assert path.exists()
    assert path == output_path

    with open(path) as f:
        data = json.load(f)
        assert "scene_0000" in data
        assert data["scene_0000"]["git_hash"] == "123"
        assert data["scene_0000"]["recipe_snapshot"]["a"] == 1
