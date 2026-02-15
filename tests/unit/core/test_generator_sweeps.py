import numpy as np

from render_tag.core.config import GenConfig
from render_tag.generation.scene import Generator


def test_generator_distance_sweep(tmp_path):
    """Verify that sampling_mode='distance' produces varying distances."""
    config = GenConfig.model_validate(
        {
            "dataset": {"num_scenes": 10},
            "camera": {"min_distance": 1.0, "max_distance": 10.0},
            "scenario": {"sampling_mode": "distance"},
        }
    )

    gen = Generator(config, output_dir=tmp_path)

    # Check first and last scene
    s0 = gen.generate_scene(0)
    s9 = gen.generate_scene(9)

    # Extrinsics extract distance
    pos0 = np.array(s0.cameras[0].transform_matrix)[:3, 3]
    dist0 = np.linalg.norm(pos0)

    pos9 = np.array(s9.cameras[0].transform_matrix)[:3, 3]
    dist9 = np.linalg.norm(pos9)

    assert abs(dist0 - 1.0) < 1e-3
    assert abs(dist9 - 10.0) < 1e-3


def test_generator_angle_sweep(tmp_path):
    """Verify that sampling_mode='angle' produces varying elevations."""
    config = GenConfig.model_validate(
        {
            "dataset": {"num_scenes": 10},
            "camera": {"min_elevation": 0.1, "max_elevation": 0.9},
            "scenario": {"sampling_mode": "angle"},
        }
    )

    gen = Generator(config, output_dir=tmp_path)

    s0 = gen.generate_scene(0)
    s9 = gen.generate_scene(9)

    # Elevation is pos[2] / norm(pos)
    pos0 = np.array(s0.cameras[0].transform_matrix)[:3, 3]
    elev0 = pos0[2] / np.linalg.norm(pos0)

    pos9 = np.array(s9.cameras[0].transform_matrix)[:3, 3]
    elev9 = pos9[2] / np.linalg.norm(pos9)

    assert abs(elev0 - 0.1) < 1e-3
    assert abs(elev9 - 0.9) < 1e-3
