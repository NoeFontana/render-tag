import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from render_tag.orchestration.experiment import load_experiment_config, expand_campaign
from render_tag.orchestration.experiment_schema import Campaign, SubExperiment

@pytest.fixture
def campaign_yaml(tmp_path):
    p = tmp_path / "campaign.yaml"
    p.write_text(f"""
output_dir: output/locus_bench_v1/01_calibration

experiments:
  - name: 01_checkerboard
    config: {tmp_path}/configs/presets/calibration/01_checkerboard.yaml
    overrides:
      dataset:
        seed: 42
        intent: calibration_cv

  - name: 02_aprilgrid
    config: {tmp_path}/configs/presets/calibration/02_aprilgrid.yaml
    overrides:
      dataset:
        intent: calibration_tag
    """)
    return p

@pytest.fixture
def preset_configs(tmp_path):
    # Mock existence of preset configs
    (tmp_path / "configs/presets/calibration").mkdir(parents=True)
    (tmp_path / "configs/presets/calibration/01_checkerboard.yaml").write_text("""
dataset:
  num_scenes: 1
  output_dir: output/ignored
camera:
  resolution: [100, 100]
    """)
    (tmp_path / "configs/presets/calibration/02_aprilgrid.yaml").write_text("""
dataset:
  num_scenes: 1
  output_dir: output/ignored
camera:
  resolution: [100, 100]
    """)
    return tmp_path

def test_load_campaign_config(campaign_yaml):
    # Test that we can load a campaign config
    # This will fail until we implement Campaign schema and loader logic
    config = load_experiment_config(campaign_yaml)
    assert isinstance(config, Campaign)
    assert Path(config.output_dir) == Path("output/locus_bench_v1/01_calibration")
    assert len(config.experiments) == 2
    assert config.experiments[0].name == "01_checkerboard"
    assert config.experiments[0].overrides["dataset"]["intent"] == "calibration_cv"

def test_expand_campaign(campaign_yaml, preset_configs):
    # Test that we can expand a campaign into variants with correct paths
    config = load_experiment_config(campaign_yaml)
    
    # We rely on the preset_configs fixture to create the yaml files on disk
    # expand_campaign will read them.
    
    from render_tag.orchestration.experiment import expand_campaign
    
    variants = expand_campaign(config)
    
    assert len(variants) == 2
    
    # Check variant 1
    v1 = variants[0]
    assert v1.experiment_name == "01_checkerboard"
    # Output dir should be <campaign_output>/<sub_exp_name>
    expected_out = Path("output/locus_bench_v1/01_calibration/01_checkerboard")
    assert v1.config.dataset.output_dir == expected_out
    # Check intent override
    assert v1.config.dataset.intent == "calibration_cv"
    
    # Check variant 2
    v2 = variants[1]
    assert v2.experiment_name == "02_aprilgrid"
    expected_out_2 = Path("output/locus_bench_v1/01_calibration/02_aprilgrid")
    assert v2.config.dataset.output_dir == expected_out_2
    assert v2.config.dataset.intent == "calibration_tag"
