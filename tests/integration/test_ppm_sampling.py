"""
Integration tests for PPM-Driven Generation.
"""

import numpy as np

from render_tag.core.config import GenConfig, PPMConstraint
from render_tag.generation.projection_math import calculate_ppm
from render_tag.generation.scene import Generator


def test_ppm_sampling_enforcement(tmp_path):
    # Setup config with PPM constraint
    config = GenConfig()
    config.tag.family = "tag36h11"
    config.tag.size_meters = 0.16
    config.camera.resolution = (1280, 720)
    config.camera.fov = 60.0
    config.camera.samples_per_scene = 1
    
    # Target PPM range: 10 to 20
    config.camera.ppm_constraint = PPMConstraint(min=10.0, max=20.0)
    
    gen = Generator(config, tmp_path)
    
    # Generate a few scenes
    num_test_scenes = 10
    recipes = [gen.generate_scene(i) for i in range(num_test_scenes)]
    
    # Grid size for tag36h11 is 8
    grid_size = 8
    # Focal length in pixels for 1280px width and 60 deg FOV
    f_px = 1280 / (2.0 * np.tan(np.radians(60.0 / 2.0)))
    
    for i, recipe in enumerate(recipes):
        # In our simple test, we have exactly one tag at [0,0,0] (or near it)
        # and one camera.
        cam = recipe.cameras[0]
        # Distance from camera to origin
        cam_pos = np.array([cam.transform_matrix[0][3], cam.transform_matrix[1][3], cam.transform_matrix[2][3]])
        dist = np.linalg.norm(cam_pos)
        
        # Calculate actual PPM
        actual_ppm = calculate_ppm(
            distance_m=dist,
            tag_size_m=0.16,
            focal_length_px=f_px,
            tag_grid_size=grid_size
        )
        
        # Should be within [10, 20] range (allowing for small tolerance due to facing angle etc)
        # Note: PPM formula uses direct distance. 
        # If the tag is tilted, PPM might vary slightly across the tag, 
        # but our solver uses the center distance.
        assert actual_ppm >= 9.9, f"Scene {i}: PPM {actual_ppm} too low (min 10.0)"
        assert actual_ppm <= 20.1, f"Scene {i}: PPM {actual_ppm} too high (max 20.0)"

def test_ppm_takes_precedence(tmp_path):
    # Setup config with PPM constraint AND conflicting distance constraints
    config = GenConfig()
    config.tag.family = "tag36h11"
    config.tag.size_meters = 0.16
    config.camera.resolution = (1280, 720)
    config.camera.fov = 60.0
    
    # PPM range 10-20 at 60deg FOV and 0.16m tag (grid 8)
    # distance = (f * 0.16) / (ppm * 8)
    # f = 1108.51
    # dist for 10ppm = 2.217m
    # dist for 20ppm = 1.108m
    
    # Set distance constraints to be FAR AWAY (e.g. 10m-20m)
    config.camera.min_distance = 10.0
    config.camera.max_distance = 20.0
    
    # BUT set PPM constraint to 10-20 (which requires 1.1m-2.2m)
    config.camera.ppm_constraint = PPMConstraint(min=10.0, max=20.0)
    
    gen = Generator(config, tmp_path)
    recipe = gen.generate_scene(0)
    
    cam = recipe.cameras[0]
    cam_pos = np.array([cam.transform_matrix[0][3], cam.transform_matrix[1][3], cam.transform_matrix[2][3]])
    dist = np.linalg.norm(cam_pos)
    
    # Distance should be in the 1.1m-2.2m range, NOT 10m-20m
    assert dist < 5.0, f"Distance {dist} suggests PPM constraint was ignored"
