import numpy as np

from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler
from render_tag.generation.projection_math import calculate_incidence_angle, get_world_matrix


def test_flying_tag_orientation():
    """Verify that in flying mode, tags are always oriented towards the camera."""
    config = GenConfig()
    config.scenario.flying = True
    config.camera.samples_per_scene = 5
    config.dataset.num_scenes = 2

    compiler = SceneCompiler(config)

    for i in range(config.dataset.num_scenes):
        recipe = compiler.compile_scene(i)

        # Get the target tag
        target_tag = next((obj for obj in recipe.objects if obj.type == "TAG"), None)
        assert target_tag is not None

        tag_world_mat = get_world_matrix(
            target_tag.location, target_tag.rotation_euler, target_tag.scale
        )

        for cam in recipe.cameras:
            cam_world_mat = np.array(cam.transform_matrix)

            # Use calculate_incidence_angle to check orientation
            angle = calculate_incidence_angle(cam_world_mat, tag_world_mat)

            # Incidence angle 0 means facing, 90 means side-on.
            # is_facing_camera uses min_dot=0.2 (~78 degrees).
            # So angle should be < 78 degrees.
            assert angle < 78.5, f"Tag in scene {i} is facing away from camera (angle: {angle:.2f})"


def test_grid_tag_orientation():
    """Verify that in grid mode, tags are always oriented towards the camera."""
    config = GenConfig()
    config.scenario.flying = False
    config.scenario.layout = "plain"
    config.scenario.grid_size = (3, 3)
    config.camera.samples_per_scene = 3

    compiler = SceneCompiler(config)
    recipe = compiler.compile_scene(0)

    # Check all tags in the grid
    for obj in recipe.objects:
        if obj.type != "TAG":
            continue

        tag_world_mat = get_world_matrix(obj.location, obj.rotation_euler, obj.scale)

        for cam in recipe.cameras:
            cam_world_mat = np.array(cam.transform_matrix)
            angle = calculate_incidence_angle(cam_world_mat, tag_world_mat)
            assert angle < 78.5, f"Tag {obj.name} is facing away from camera (angle: {angle:.2f})"
