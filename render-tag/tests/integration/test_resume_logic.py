from typer.testing import CliRunner

from render_tag.cli import app

runner = CliRunner()


def test_resume_skips_completed_scenes(tmp_path):
    """
    Integration test for --resume flag.
    1. Run a partial generation or mock it by creating sidecars.
    2. Run with --resume and verify it skips those scenes.
    """
    output_dir = tmp_path / "resume_test"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True)

    # Mock scene 0 as completed
    # We need a valid-ish provenance JSON for the validator/generator to not complain?
    # Actually cli.py just checks for existence of scene_(\d+)_meta.json
    (images_dir / "scene_0000_meta.json").write_text('{"scene_id": 0}')

    # Run generate for 2 scenes with --resume
    # We use --skip-render to avoid needing Blender for this logic test
    result = runner.invoke(
        app,
        [
            "generate",
            "--config",
            "configs/test_minimal.yaml",
            "--output",
            str(output_dir),
            "--scenes",
            "2",
            "--resume",
            "--skip-render",
        ],
    )

    assert result.exit_code == 0
    assert "Found 1 completed scenes" in result.stdout

    # Check that only recipes_shard_0.json was updated with scene 1
    recipe_path = output_dir / "recipes_shard_0.json"
    assert recipe_path.exists()

    import json

    with open(recipe_path) as f:
        recipes = json.load(f)

    # Should only contain scene 1
    scene_ids = [r["scene_id"] for r in recipes]
    assert 0 not in scene_ids
    assert 1 in scene_ids
    assert len(scene_ids) == 1
