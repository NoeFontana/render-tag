"""
Integration tests for PPM-Driven Generation.
"""

import numpy as np

from render_tag.core.config import GenConfig, PPMConstraint
from render_tag.generation.compiler import SceneCompiler
from render_tag.generation.projection_math import calculate_ppm


def test_ppm_sampling_enforcement(tmp_path):
    # Setup config with PPM constraint
    config = GenConfig()
    config.tag.family = "tag36h11"
    config.tag.size_meters = 0.16

    # Ensure polymorphic subject is also updated (Staff Engineer sync pattern)
    from render_tag.core.schema.subject import TagSubjectConfig

    config.scenario.subject.root = TagSubjectConfig(
        tag_families=["tag36h11"], size_meters=0.16, tags_per_scene=1
    )

    config.camera.resolution = (1280, 720)
    config.camera.fov = 60.0
    config.camera.samples_per_scene = 1

    # Target PPM range: 10 to 20
    config.camera.ppm_constraint = PPMConstraint(min=10.0, max=20.0)

    compiler = SceneCompiler(config)

    # Generate a few scenes
    num_test_scenes = 10
    recipes = [compiler.compile_scene(i) for i in range(num_test_scenes)]

    # Grid size for tag36h11 is 8
    grid_size = 8
    # Focal length in pixels for 1280px width and 60 deg FOV
    f_px = 1280 / (2.0 * np.tan(np.radians(60.0 / 2.0)))

    for i, recipe in enumerate(recipes):
        # In our simple test, we have exactly one tag and one camera.
        cam = recipe.cameras[0]
        tag_obj = next((obj for obj in recipe.objects if obj.type == "TAG"), None)
        assert tag_obj is not None, "Expected at least one tag"
        
        # Distance from camera to tag center
        cam_pos = np.array(
            [cam.transform_matrix[0][3], cam.transform_matrix[1][3], cam.transform_matrix[2][3]]
        )
        tag_pos = np.array(tag_obj.location)
        dist = np.linalg.norm(cam_pos - tag_pos)

        # Calculate actual PPM using black border size
        # tag36h11 has 8x8 grid. Default margin is 1 bit. Total bits = 10.
        # Black border size = 0.16 * (8 / 10) = 0.128
        black_border_size = 0.16 * (8 / 10)
        actual_ppm = calculate_ppm(
            distance_m=dist,
            tag_size_m=black_border_size,
            focal_length_px=f_px,
            tag_grid_size=grid_size,
        )
        # Should be within [10, 20] range (allowing for small tolerance due to facing angle etc)
        # Note: PPM formula uses direct distance.
        assert actual_ppm >= 9.9, f"Scene {i}: PPM {actual_ppm} too low (min 10.0)"
        assert actual_ppm <= 20.1, f"Scene {i}: PPM {actual_ppm} too high (max 20.0)"


def test_ppm_takes_precedence(tmp_path):
    # Setup config with PPM constraint AND conflicting distance constraints
    config = GenConfig()
    config.tag.family = "tag36h11"
    config.tag.size_meters = 0.16

    from render_tag.core.schema.subject import TagSubjectConfig

    config.scenario.subject.root = TagSubjectConfig(
        tag_families=["tag36h11"], size_meters=0.16, tags_per_scene=1
    )

    config.camera.resolution = (1280, 720)
    config.camera.fov = 60.0

    # Distance constraints set to be inclusive of the PPM target
    config.camera.min_distance = 0.5
    config.camera.max_distance = 20.0

    # BUT set PPM constraint to 10-20 (which requires approx 1.1m-2.2m)
    config.camera.ppm_constraint = PPMConstraint(min=10.0, max=20.0)

    compiler = SceneCompiler(config)
    recipe = compiler.compile_scene(0)

    cam = recipe.cameras[0]
    tag_obj = next((obj for obj in recipe.objects if obj.type == "TAG"), None)
    assert tag_obj is not None, "Expected at least one tag"
    tag_pos = np.array(tag_obj.location)

    cam_pos = np.array(
        [cam.transform_matrix[0][3], cam.transform_matrix[1][3], cam.transform_matrix[2][3]]
    )
    dist = np.linalg.norm(cam_pos - tag_pos)

    # Distance should be in the 1.1m-2.2m range
    assert 1.0 < dist < 3.0, f"Distance {dist} suggests PPM constraint was ignored or misclamped"
