import json
from unittest.mock import MagicMock

from render_tag.backend.engine import RenderContext, execute_recipe
from render_tag.data_io.writers import ProvenanceWriter


def test_provenance_manifest_generated(tmp_path, stabilized_bridge):
    """
    Staff Engineer: Verify that the unified provenance manifest is generated.
    Using direct execute_recipe call for speed and reliability.
    """
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    # Minimal recipe
    from render_tag.core.schema.recipe import SceneRecipe

    recipe = SceneRecipe(
        scene_id=0,
        random_seed=42,
        renderer={"mode": "workbench"},
        cameras=[
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "intrinsics": {
                    "resolution": [128, 128],
                    "k_matrix": [[1, 0, 64], [0, 1, 64], [0, 0, 1]],
                    "fov": 60.0,
                },
            }
        ],
        objects=[],
        world={},
    )

    # Mock writers
    provenance_writer = ProvenanceWriter(output_dir / "provenance_shard_0.json")

    ctx = RenderContext(
        output_dir=output_dir,
        renderer_mode="workbench",
        csv_writer=MagicMock(),
        coco_writer=MagicMock(),
        rich_writer=MagicMock(),
        provenance_writer=provenance_writer,
        global_seed=42,
        skip_visibility=True,
    )

    execute_recipe(recipe, ctx)

    # Finalize provenance writer (usually handled by worker_server finalize_writers)
    provenance_writer.save()

    # Check manifest
    manifest_path = output_dir / "provenance_shard_0.json"
    assert manifest_path.exists(), "Provenance manifest not found"

    with open(manifest_path) as f:
        master_data = json.load(f)
        # It's a mapping of image_id -> provenance
        image_id = "scene_0000_cam_0000"
        assert image_id in master_data
        data = master_data[image_id]
        assert "git_hash" in data
        assert "timestamp" in data
        assert "recipe_snapshot" in data
        assert data["recipe_snapshot"]["scene_id"] == 0
