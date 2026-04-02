import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from render_tag.backend.engine import (
    RenderContext,
    _extract_and_save_ground_truth,
    execute_recipe,
)
from render_tag.core.config import GenConfig
from render_tag.core.schema import DetectionRecord
from render_tag.core.schema.recipe import SceneRecipe
from render_tag.data_io.writers import ProvenanceWriter
from render_tag.generation.compiler import SceneCompiler


def test_sequence_defaults_validate():
    """Sequence config should default to a disabled, valid mode."""
    config = GenConfig()

    assert config.sequence.enabled is False
    assert config.sequence.frames_per_sequence == 8
    assert config.sequence.fps == 30
    assert config.camera.sensor_dynamics.blur_profile == "off"


def test_sequence_compiler_emits_ordered_frames_and_velocity():
    """Sequence mode should emit temporally ordered cameras with finite-difference velocity."""
    config = GenConfig()
    config.camera.samples_per_scene = 1
    config.camera.min_distance = 0.75
    config.camera.max_distance = 1.0
    config.scenario.subject.root.tags_per_scene = 1
    config.sequence.enabled = True
    config.sequence.frames_per_sequence = 4
    config.sequence.fps = 20
    config.sequence.max_translation_per_frame_m = 0.01
    config.sequence.max_yaw_deg_per_frame = 1.0
    config.camera.sensor_dynamics.blur_profile = "light"
    config.camera.sensor_dynamics.shutter_time_ms = 6.0
    config.camera.sensor_dynamics.rolling_shutter_duration_ms = 3.0

    compiler = SceneCompiler(config, global_seed=42)
    recipe = compiler.compile_scene(0)

    cameras = recipe.cameras
    assert len(cameras) == 4

    timestamps = np.array([cam.timestamp_s for cam in cameras], dtype=float)
    np.testing.assert_allclose(timestamps, np.array([0.003, 0.053, 0.103, 0.153]), atol=1e-8)

    for idx, cam in enumerate(cameras):
        assert cam.frame_index == idx
        assert cam.sensor_dynamics is not None
        assert cam.sensor_dynamics.blur_profile == "light"
        assert cam.sensor_dynamics.rolling_shutter_duration_ms == 0.0

    transforms = [np.array(cam.transform_matrix, dtype=float) for cam in cameras]
    first_loc = transforms[0][:3, 3]
    assert cameras[0].sequence_pose_delta == [0.0, 0.0, 0.0]
    assert cameras[0].sensor_dynamics.velocity == [0.0, 0.0, 0.0]

    for idx in range(1, len(cameras)):
        loc = transforms[idx][:3, 3]
        prev_loc = transforms[idx - 1][:3, 3]
        delta = loc - prev_loc
        sequence_pose_delta = np.array(cameras[idx].sequence_pose_delta, dtype=float)
        velocity = np.array(cameras[idx].sensor_dynamics.velocity, dtype=float)
        np.testing.assert_allclose(sequence_pose_delta, delta, atol=1e-8)
        np.testing.assert_allclose(
            velocity,
            delta * config.sequence.fps,
            atol=1e-8,
        )
        assert not np.allclose(loc, first_loc)


def test_sequence_provenance_includes_frame_metadata(tmp_path, stabilized_bridge):
    """Rendered sequence frames should persist ordering metadata in provenance."""
    recipe = SceneRecipe(
        scene_id=0,
        random_seed=42,
        renderer={"mode": "workbench"},
        cameras=[
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "intrinsics": {
                    "resolution": [64, 64],
                    "k_matrix": [[1, 0, 32], [0, 1, 32], [0, 0, 1]],
                    "fov": 60.0,
                },
                "frame_index": 0,
                "timestamp_s": 0.0,
                "sequence_pose_delta": [0.0, 0.0, 0.0],
                "sensor_dynamics": {"blur_profile": "light", "velocity": [0.0, 0.0, 0.0]},
            },
            {
                "transform_matrix": [[1, 0, 0, 0.01], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "intrinsics": {
                    "resolution": [64, 64],
                    "k_matrix": [[1, 0, 32], [0, 1, 32], [0, 0, 1]],
                    "fov": 60.0,
                },
                "frame_index": 1,
                "timestamp_s": 0.1,
                "sequence_pose_delta": [0.01, 0.0, 0.0],
                "sensor_dynamics": {"blur_profile": "light", "velocity": [0.1, 0.0, 0.0]},
            },
        ],
        objects=[],
        world={},
    )

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    provenance_writer = ProvenanceWriter(output_dir / "provenance_shard_0.json")

    ctx = RenderContext(
        output_dir=output_dir,
        renderer_mode="workbench",
        csv_writer=MagicMock(),
        coco_writer=MagicMock(),
        rich_writer=MagicMock(),
        provenance_writer=provenance_writer,
        global_seed=42,
        skip_visibility=True,
    )

    execute_recipe(recipe, ctx)
    provenance_writer.save()

    with open(output_dir / "provenance_shard_0.json") as f:
        data = json.load(f)

    assert "scene_0000_cam_0000" in data
    assert "scene_0000_cam_0001" in data
    assert data["scene_0000_cam_0000"]["sequence"]["frame_index"] == 0
    assert data["scene_0000_cam_0001"]["sequence"]["frame_index"] == 1
    assert data["scene_0000_cam_0000"]["sequence"]["frames_per_sequence"] == 2
    assert data["scene_0000_cam_0000"]["sequence"]["fps"] == 10.0
    assert data["scene_0000_cam_0000"]["sequence"]["ground_truth_pose_time"] == "mid_exposure"
    assert data["scene_0000_cam_0000"]["sequence"]["image_geometry_time"] == "mid_exposure"
    assert data["scene_0000_cam_0000"]["sequence"]["observation_model"] == "motion_blurred"
    assert data["scene_0000_cam_0000"]["sequence"]["exposure_midpoint_s"] == 0.0


def test_sequence_rich_truth_uses_mid_exposure_metadata(tmp_path):
    """Rich truth records should encode the midpoint timing contract for blurred observations."""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    ctx = RenderContext(
        output_dir=output_dir,
        renderer_mode="workbench",
        csv_writer=MagicMock(),
        coco_writer=MagicMock(),
        rich_writer=MagicMock(),
        provenance_writer=ProvenanceWriter(output_dir / "provenance_shard_0.json"),
        global_seed=42,
        skip_visibility=True,
    )
    cam_recipe = SceneRecipe(
        scene_id=0,
        random_seed=42,
        renderer={"mode": "workbench"},
        cameras=[
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 1]],
                "intrinsics": {
                    "resolution": [64, 64],
                    "k_matrix": [[40, 0, 32], [0, 40, 32], [0, 0, 1]],
                    "fov": 60.0,
                },
                "frame_index": 0,
                "timestamp_s": 0.103,
                "sensor_dynamics": {
                    "blur_profile": "light",
                    "velocity": [0.1, 0.0, 0.0],
                    "shutter_time_ms": 6.0,
                },
            }
        ],
        objects=[],
        world={},
    ).cameras[0]

    detection = DetectionRecord(
        image_id="scene_0000_cam_0000",
        tag_id=0,
        tag_family="tag36h11",
        corners=[(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)],
    )

    with patch(
        "render_tag.backend.engine.generate_subject_records",
        return_value=[detection],
    ):
        fake_obj = MagicMock()
        fake_obj.blender_obj.get.return_value = "TAG"
        _extract_and_save_ground_truth(
            [fake_obj],
            "scene_0000_cam_0000",
            1,
            [64, 64],
            ctx,
            MagicMock(),
            cam_recipe,
        )

    det = ctx.rich_writer.add_detection.call_args.args[0]
    assert det.metadata["ground_truth_pose_time"] == "mid_exposure"
    assert det.metadata["image_geometry_time"] == "mid_exposure"
    assert det.metadata["observation_model"] == "motion_blurred"
    assert det.metadata["timestamp_s"] == 0.103
    assert det.metadata["exposure_midpoint_s"] == 0.103
    assert det.metadata["exposure_start_s"] == pytest.approx(0.1)
    assert det.metadata["exposure_end_s"] == pytest.approx(0.106)
