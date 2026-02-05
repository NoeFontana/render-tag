
from render_tag.config import GenConfig
from render_tag.generator import Generator


def test_generator_determinism(tmp_path):
    config = GenConfig()
    config.dataset.seeds.global_seed = 12345
    
    gen = Generator(config, tmp_path)
    
    # Generate scene 0 twice
    recipe1 = gen.generate_scene(0)
    recipe2 = gen.generate_scene(0)
    
    assert recipe1.model_dump_json() == recipe2.model_dump_json()
    
    # Generate scene 1
    recipe3 = gen.generate_scene(1)
    assert recipe1.model_dump_json() != recipe3.model_dump_json()

def test_sharding_invariance(tmp_path):
    """Test that scenes generated via sharded calls match global calls."""
    config = GenConfig()
    config.dataset.seeds.global_seed = 12345
    
    gen = Generator(config, tmp_path)
    
    # Global: Scene 5
    scene5_global = gen.generate_scene(5)
    
    # Sharded: Shard 1 of 2 (Total 10 scenes -> 5 per shard. Shard 1 starts at 5)
    # scenes_per_shard = 5. start_idx = 1 * 5 = 5.
    recipes_shard = gen.generate_shards(10, 1, 2)
    scene5_shard = recipes_shard[0] # First scene in shard 1 is scene 5
    
    assert scene5_global.scene_id == 5
    assert scene5_shard.scene_id == 5
    
    # Crucial: Content must match
    assert scene5_global.model_dump_json() == scene5_shard.model_dump_json()
