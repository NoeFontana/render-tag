from render_tag.core.schema import (
    CameraIntrinsics,
    CameraRecipe,
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
