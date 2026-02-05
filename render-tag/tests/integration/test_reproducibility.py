import subprocess
import pytest
import filecmp
import json
import yaml
from pathlib import Path

@pytest.mark.integration
def test_reproducibility_benchmark(tmp_path):
    """Verify that running generation twice produces bit-identical images at low resolution."""
    # Create a tiny resolution config to make rendering fast
    config = {
        "camera": {
            "resolution": [32, 32],
            "samples_per_scene": 1
        }
    }
    config_path = tmp_path / "tiny_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    
    # Run 1
    subprocess.run([
        "render-tag", "generate", 
        "--config", str(config_path),
        "--output", str(out1),
        "--scenes", "1",
        "--seed", "12345"
    ], check=True)
    
    # Run 2
    subprocess.run([
        "render-tag", "generate", 
        "--config", str(config_path),
        "--output", str(out2),
        "--scenes", "1",
        "--seed", "12345"
    ], check=True)
    
    # Compare image
    img1 = out1 / "images/scene_0000_cam_0000.png"
    img2 = out2 / "images/scene_0000_cam_0000.png"
    assert filecmp.cmp(img1, img2), "Images differ - determinism failed"

@pytest.mark.integration
def test_shard_invariance_fast(tmp_path):
    """Verify that splitting a job into shards does not change recipes (Fast version)."""
    # Create safe config
    config_path = tmp_path / "safe_config.yaml"
    config_path.write_text("scene:\n  background_hdri: null\n  texture_dir: null\n")

    # We use --skip-render to only verify the recipe logic
    out_single = tmp_path / "single"
    subprocess.run([
        "render-tag", "generate",
        "--config", str(config_path),
        "--output", str(out_single),
        "--scenes", "4",
        "--seed", "999",
        "--total-shards", "1", "--shard-index", "0",
        "--skip-render"
    ], check=True)
    
    out_shard0 = tmp_path / "shard0"
    out_shard1 = tmp_path / "shard1"
    
    subprocess.run([
        "render-tag", "generate",
        "--config", str(config_path),
        "--output", str(out_shard0),
        "--scenes", "4",
        "--seed", "999",
        "--total-shards", "2", "--shard-index", "0",
        "--skip-render"
    ], check=True)
    
    subprocess.run([
        "render-tag", "generate",
        "--config", str(config_path),
        "--output", str(out_shard1),
        "--scenes", "4",
        "--seed", "999",
        "--total-shards", "2", "--shard-index", "1",
        "--skip-render"
    ], check=True)
    
    # Load and compare scene recipes
    with open(out_single / "recipes_shard_0.json") as f: recipes_s = json.load(f)
    with open(out_shard0 / "recipes_shard_0.json") as f: recipes_m0 = json.load(f)
    with open(out_shard1 / "recipes_shard_1.json") as f: recipes_m1 = json.load(f)
    
    # Scene 0 (in shard 0)
    assert recipes_s[0]["scene_id"] == 0
    assert recipes_m0[0]["scene_id"] == 0
    assert recipes_s[0] == recipes_m0[0]
    
    # Scene 2 (in shard 1)
    assert recipes_s[2]["scene_id"] == 2
    assert recipes_m1[0]["scene_id"] == 2
    assert recipes_s[2] == recipes_m1[0]
