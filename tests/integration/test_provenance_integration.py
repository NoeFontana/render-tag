import json
from unittest.mock import MagicMock

from render_tag.backend.engine import RenderContext, execute_recipe


def test_provenance_sidecar_generated(tmp_path, stabilized_bridge):
    """
    Staff Engineer: Verify that sidecar JSON files are generated with images.
    Using direct execute_recipe call for speed and reliability.
    """
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    # Minimal recipe
    recipe = {
        "scene_id": 0,
        "renderer": {"mode": "workbench"},
        "cameras": [
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "intrinsics": {"resolution": [128, 128], "fov": 60.0},
            }
        ],
        "objects": [],
        "world": {},
    }

    # Mock writers
    from render_tag.data_io.writers import SidecarWriter

    sidecar_writer = SidecarWriter(output_dir)

    ctx = RenderContext(
        output_dir=output_dir,
        renderer_mode="workbench",
        csv_writer=MagicMock(),
        coco_writer=MagicMock(),
        rich_writer=MagicMock(),
        sidecar_writer=sidecar_writer,
        global_seed=42,
        skip_visibility=True,
    )

    execute_recipe(recipe, ctx)

    # Check sidecar
    sidecar_path = output_dir / "images/scene_0000_cam_0000_meta.json"
    assert sidecar_path.exists(), "Sidecar file not found"

    with open(sidecar_path) as f:
        data = json.load(f)
        assert "git_hash" in data
        assert "timestamp" in data
        assert "recipe_snapshot" in data
        assert data["recipe_snapshot"]["scene_id"] == 0
