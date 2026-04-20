import numpy as np

from render_tag.core.config import GenConfig
from render_tag.core.geometry.projection_math import calculate_incidence_angle, get_world_matrix
from render_tag.generation.compiler import SceneCompiler


def test_flying_tag_orientation():
    """Verify that in flying mode, tags are always oriented towards the camera."""
    from render_tag.core.schema.subject import TagSubjectConfig

    config = GenConfig()
    config.scenario.flying = True

    # Staff Engineer: Force 1 tag to ensure unambiguous target-to-camera check
    config.scenario.subject.root = TagSubjectConfig(
        tag_families=["tag36h11"], size_mm=100.0, tags_per_scene=1
    )

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
            # is_facing_camera uses min_dot=0.1 (~84.2 degrees).
            # So angle should be < 84.5 degrees.
            assert angle < 84.5, f"Tag in scene {i} is facing away from camera (angle: {angle:.2f})"


def test_grid_tag_orientation():
    """Verify that in grid mode, tags are always oriented towards the camera."""
    config = GenConfig()
    config.scenario.flying = False
    # Use TAGS subject
    from render_tag.core.schema.subject import TagSubjectConfig

    config.scenario.subject.root = TagSubjectConfig(tag_families=["tag36h11"], size_mm=100.0)

    # Grid size etc is now handled by the compiler's internal logic for TAGS
    # or will be added to TagSubjectConfig in Phase 2 if needed.
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
            assert angle < 84.5, f"Tag {obj.name} is facing away from camera (angle: {angle:.2f})"
