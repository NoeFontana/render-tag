import json
from pathlib import Path

from render_tag.core.config import GenConfig
from render_tag.generation.scene import Generator


def test_generator_reproducibility(tmp_path):
    """Verify that Generator produces identical scene_recipes.json for same seed."""
    config = GenConfig(version="0.1")
    config.dataset.num_scenes = 5
    seed = 98765
    
    out1 = tmp_path / "run1"
    gen1 = Generator(config, out1, global_seed=seed)
    recipes1 = gen1.generate_all()
    path1 = gen1.save_recipe_json(recipes1)
    
    out2 = tmp_path / "run2"
    gen2 = Generator(config, out2, global_seed=seed)
    recipes2 = gen2.generate_all()
    path2 = gen2.save_recipe_json(recipes2)
    
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
    
    # Verify different seeds produce different recipes
    out3 = tmp_path / "run3"
    gen3 = Generator(config, out3, global_seed=seed + 1)
    recipes3 = gen3.generate_all()
    path3 = gen3.save_recipe_json(recipes3)
    
    with open(path3) as f3:
        data3 = json.load(f3)
        
    assert data1 != data3
