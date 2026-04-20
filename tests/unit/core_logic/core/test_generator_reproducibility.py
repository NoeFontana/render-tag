import json
from pathlib import Path

from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler


def test_compiler_reproducibility(tmp_path):
    """SceneCompiler produces identical scene_recipes.json for the same seed."""
    config = GenConfig(version="0.1")
    config.dataset.num_scenes = 5
    seed = 98765

    out1 = tmp_path / "run1"
    c1 = SceneCompiler(config, global_seed=seed, output_dir=out1)
    recipes1 = c1.compile_shards(shard_index=0, total_shards=1, validate=True)
    path1 = c1.save_recipe_json(recipes1)

    out2 = tmp_path / "run2"
    c2 = SceneCompiler(config, global_seed=seed, output_dir=out2)
    recipes2 = c2.compile_shards(shard_index=0, total_shards=1, validate=True)
    path2 = c2.save_recipe_json(recipes2)

    with open(path1) as f1, open(path2) as f2:
        data1 = json.load(f1)
        data2 = json.load(f2)

    def normalize_paths(data):
        for scene in data:
            for obj in scene.get("objects", []):
                if obj.get("texture_path"):
                    obj["texture_path"] = Path(obj["texture_path"]).name
        return data

    assert normalize_paths(data1) == normalize_paths(data2)

    # Different seeds must diverge.
    out3 = tmp_path / "run3"
    c3 = SceneCompiler(config, global_seed=seed + 1, output_dir=out3)
    recipes3 = c3.compile_shards(shard_index=0, total_shards=1, validate=True)
    path3 = c3.save_recipe_json(recipes3)

    with open(path3) as f3:
        data3 = json.load(f3)

    assert data1 != data3
