"""
Unit tests for configuration module.
"""

import tempfile
from pathlib import Path

import pytest

from render_tag.core.config import (
    CameraConfig,
    CameraIntrinsics,
    DatasetConfig,
    GenConfig,
    LightingConfig,
    PhysicsConfig,
    SeedConfig,
    TagConfig,
    TagFamily,
    load_config,
)


class TestDatasetConfig:
    def test_defaults(self) -> None:
        config = DatasetConfig()
        assert config.output_dir == Path("output")
        assert config.seed == 42

    def test_negative_seed_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetConfig(seeds=SeedConfig(global_seed=-1))


class TestCameraIntrinsics:
    def test_defaults(self) -> None:
        intrinsics = CameraIntrinsics()
        assert intrinsics.k_matrix is None
        assert intrinsics.k1 == 0.0

    def test_valid_k_matrix(self) -> None:
        k = [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]
        intrinsics = CameraIntrinsics(k_matrix=k)
        assert intrinsics.k_matrix == k

    def test_invalid_k_matrix_size(self) -> None:
        with pytest.raises(ValueError, match="K matrix must be 3x3"):
            CameraIntrinsics(k_matrix=[[1, 2], [3, 4]])

    def test_invalid_k_matrix_last_row(self) -> None:
        k = [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.1, 0.0, 1.0]]
        with pytest.raises(ValueError, match="last row must be"):
            CameraIntrinsics(k_matrix=k)

    def test_distortion_coeffs(self) -> None:
        # Brown-Conrady: must set distortion_model to get coefficients
        bc = CameraIntrinsics(
            distortion_model="brown_conrady", k1=0.1, k2=0.2, p1=0.01, p2=0.02, k3=0.3
        )
        assert bc.get_distortion_coeffs() == (0.1, 0.2, 0.01, 0.02, 0.3)

        # Kannala-Brandt
        kb = CameraIntrinsics(
            distortion_model="kannala_brandt", kb1=0.1, kb2=0.05, kb3=0.01, kb4=0.001
        )
        assert kb.get_distortion_coeffs() == (0.1, 0.05, 0.01, 0.001)

        # None model returns empty tuple regardless of coefficients set
        assert CameraIntrinsics(k1=0.1).get_distortion_coeffs() == ()


class TestCameraConfig:
    def test_defaults(self) -> None:
        config = CameraConfig()
        assert config.resolution == (1920, 1080)
        assert config.width == 1920
        assert config.height == 1080
        assert config.fov == 70.0
        assert config.samples_per_scene == 10

    def test_invalid_resolution(self) -> None:
        with pytest.raises(ValueError):
            CameraConfig(resolution=(0, 480))

    def test_invalid_fov(self) -> None:
        with pytest.raises(ValueError):
            CameraConfig(fov=0)
        with pytest.raises(ValueError):
            CameraConfig(fov=180)

    def test_k_matrix_from_explicit(self) -> None:
        k = [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]
        config = CameraConfig(intrinsics=CameraIntrinsics(k_matrix=k))
        assert config.get_k_matrix() == k

    def test_k_matrix_from_focal_length(self) -> None:
        config = CameraConfig(
            resolution=(640, 480), intrinsics=CameraIntrinsics(focal_length=500.0)
        )
        k = config.get_k_matrix()
        assert k[0][0] == 500.0  # fx
        assert k[1][1] == 500.0  # fy
        assert k[0][2] == 320.0  # cx (centered: 640/2)
        assert k[1][2] == 240.0  # cy (centered: 480/2)

    def test_k_matrix_from_fov(self) -> None:
        config = CameraConfig(resolution=(640, 480), fov=90.0)
        k = config.get_k_matrix()
        # For 90 degree FOV: fx = width / (2 * tan(45)) = 640 / 2 = 320
        assert abs(k[0][0] - 320.0) < 0.1


class TestLightingConfig:
    def test_defaults(self) -> None:
        config = LightingConfig()
        assert config.intensity_min == 50.0
        assert config.intensity_max == 500.0

    def test_min_greater_than_max_rejected(self) -> None:
        with pytest.raises(ValueError, match="intensity_min must be <= intensity_max"):
            LightingConfig(intensity_min=100, intensity_max=50)


class TestTagFamily:
    def test_apriltag_families(self) -> None:
        assert TagFamily.TAG36H11.value == "tag36h11"
        assert TagFamily.TAG25H9.value == "tag25h9"
        assert TagFamily.TAG16H5.value == "tag16h5"

    def test_aruco_families(self) -> None:
        assert TagFamily.ARUCO_4X4_50.value == "DICT_4X4_50"
        assert TagFamily.ARUCO_6X6_250.value == "DICT_6X6_250"
        assert TagFamily.ARUCO_ORIGINAL.value == "DICT_ARUCO_ORIGINAL"

    def test_is_apriltag_property(self) -> None:
        assert TagFamily.TAG36H11.is_apriltag is True
        assert TagFamily.TAG16H5.is_apriltag is True
        assert TagFamily.ARUCO_4X4_50.is_apriltag is False

    def test_is_aruco_property(self) -> None:
        assert TagFamily.ARUCO_4X4_50.is_aruco is True
        assert TagFamily.ARUCO_ORIGINAL.is_aruco is True
        assert TagFamily.TAG36H11.is_aruco is False

    def test_config_and_schema_share_same_tagfamily(self) -> None:
        """Ensure config and schema TagFamily are the same class."""
        from render_tag.core.schema.base import TagFamily as SchemaTagFamily

        assert TagFamily is SchemaTagFamily


class TestTagConfig:
    def test_defaults(self) -> None:
        # TagConfig no longer carries subject fields — those live in ScenarioConfig.subject.
        config = TagConfig()
        assert config.margin_bits == 1


class TestPhysicsConfig:
    def test_defaults(self) -> None:
        config = PhysicsConfig()
        assert config.drop_height == 0.2
        assert config.scatter_radius == 0.5


class TestGenConfig:
    def test_defaults(self) -> None:
        config = GenConfig()
        assert config.dataset.seed == 42
        assert config.camera.fov == 70.0
        # Subject defaults to TAGS(tag36h11, 100mm)
        assert config.scenario.subject is not None
        assert config.scenario.subject.root.tag_families == ["tag36h11"]


class TestLoadConfig:
    def test_load_nested_config(self) -> None:
        yaml_content = """
dataset:
  seeds:
    global_seed: 123
camera:
  resolution: [1920, 1080]
  fov: 75.0
scenario:
  subject:
    type: TAGS
    tag_families: [tag36h11]
    size_mm: 200.0
    tags_per_scene: 3
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = load_config(Path(f.name))

        assert config.dataset.seed == 123
        assert config.camera.resolution == (1920, 1080)
        assert config.camera.fov == 75.0
        assert config.scenario.subject.root.size_mm == 200.0

    def test_load_flat_config_legacy(self) -> None:
        yaml_content = """
resolution: [640, 480]
samples: 10
tag_family: "tag36h11"
lighting:
  intensity_min: 50
  intensity_max: 500
physics:
  drop_height: 1.5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            # Flat layout with legacy tag_family triggers ACL migration + deprecation.
            with pytest.warns(DeprecationWarning):
                config = load_config(Path(f.name))

        assert config.camera.resolution == (640, 480)
        assert config.camera.samples_per_scene == 10
        assert config.physics.drop_height == 1.5

    def test_load_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))

    def test_load_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            config = load_config(Path(f.name))

        # Should use all defaults
        assert config.dataset.seed == 42
