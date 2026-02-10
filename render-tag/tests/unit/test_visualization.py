from render_tag.data_io.visualization import ShadowRenderer
from render_tag.schema import (
    CameraIntrinsics,
    CameraRecipe,
    NoiseType,
    SceneRecipe,
    SensorNoiseConfig,
)


def test_shadow_renderer_runs(tmp_path):
    cam = CameraRecipe(
        transform_matrix=[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        intrinsics=CameraIntrinsics(resolution=[640, 480]),
        sensor_noise=SensorNoiseConfig(model=NoiseType.SALT_AND_PEPPER),
    )
    recipe = SceneRecipe(scene_id=0, cameras=[cam])

    renderer = ShadowRenderer(recipe)
    # Just render to file to verify no errors
    renderer.render(output_path=tmp_path / "viz.png")
