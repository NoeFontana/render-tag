from render_tag.core.schema import (
    CameraIntrinsics,
    CameraRecipe,
    ObjectRecipe,
    SceneRecipe,
)
from render_tag.data_io.visualization import ShadowRenderer


def test_shadow_renderer_runs(tmp_path):
    cam = CameraRecipe(
        transform_matrix=[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        intrinsics=CameraIntrinsics(
            resolution=[640, 480], k_matrix=[[500, 0, 320], [0, 500, 240], [0, 0, 1]]
        ),
        iso_noise=0.1,  # Using iso_noise instead of SensorNoiseConfig if that's what's in schema
    )
    recipe = SceneRecipe(scene_id=0, random_seed=42, cameras=[cam])

    renderer = ShadowRenderer(recipe)
    # Just render to file to verify no errors
    renderer.render(output_path=tmp_path / "viz.png")


def test_shadow_renderer_draws_occluders(tmp_path):
    occluder = ObjectRecipe(
        type="OCCLUDER",
        name="Occluder_0",
        location=[0.02, 0.02, 0.03],
        rotation_euler=[0.0, 0.0, 0.7853981633974483],
        scale=[1.0, 1.0, 1.0],
        properties={
            "shape": "rod",
            "width_m": 0.003,
            "length_m": 0.15,
            "albedo": 0.05,
            "roughness": 0.9,
        },
    )
    recipe = SceneRecipe(scene_id=0, random_seed=42, objects=[occluder])

    renderer = ShadowRenderer(recipe)
    renderer.render(output_path=tmp_path / "viz_occluder.png")
    assert (tmp_path / "viz_occluder.png").exists()
