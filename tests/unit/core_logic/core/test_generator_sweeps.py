import numpy as np

from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler


def test_generator_distance_sweep(tmp_path):
    """Verify that sampling_mode='distance' produces varying distances."""
    config = GenConfig.model_validate(
        {
            "dataset": {"num_scenes": 10},
            "camera": {"min_distance": 0.5, "max_distance": 10.0},
            "scenario": {"sampling_mode": "distance"},
        }
    )

    compiler = SceneCompiler(config)

    # Check first and last scene
    s0 = compiler.compile_scene(0)
    s9 = compiler.compile_scene(9)

    # Extrinsics extract distance
    pos0 = np.array(s0.cameras[0].transform_matrix)[:3, 3]
    dist0 = np.linalg.norm(pos0)

    pos9 = np.array(s9.cameras[0].transform_matrix)[:3, 3]
    dist9 = np.linalg.norm(pos9)

    assert abs(dist0 - 0.5) < 1e-3
    assert abs(dist9 - 10.0) < 1e-3


def test_generator_angle_sweep(tmp_path):
    """Verify that sampling_mode='angle' produces varying elevations."""
    config = GenConfig.model_validate(
        {
            "dataset": {"num_scenes": 10},
            "camera": {"min_elevation": 0.3, "max_elevation": 0.9},
            "scenario": {"sampling_mode": "angle"},
        }
    )

    compiler = SceneCompiler(config)

    s0 = compiler.compile_scene(0)
    s9 = compiler.compile_scene(9)

    # Elevation is pos[2] / norm(pos)
    pos0 = np.array(s0.cameras[0].transform_matrix)[:3, 3]
    elev0 = pos0[2] / np.linalg.norm(pos0)

    pos9 = np.array(s9.cameras[0].transform_matrix)[:3, 3]
    elev9 = pos9[2] / np.linalg.norm(pos9)

    assert abs(elev0 - 0.3) < 1e-3
    assert abs(elev9 - 0.9) < 1e-3
