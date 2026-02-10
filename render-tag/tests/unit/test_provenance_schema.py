from render_tag.schema import SceneProvenance


def test_provenance_schema_validation():
    prov = SceneProvenance(
        git_hash="abcdef", timestamp="2023-01-01T12:00:00", recipe_snapshot={"scene_id": 1}
    )
    assert prov.git_hash == "abcdef"
    assert prov.recipe_snapshot["scene_id"] == 1
