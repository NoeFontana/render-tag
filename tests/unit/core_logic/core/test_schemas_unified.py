import pytest
from pydantic import ValidationError

from render_tag.core.schema import (
    BoardConfig,
    RendererConfig,
)
from render_tag.core.schema.subject import BoardSubjectConfig, TagSubjectConfig
from render_tag.core.schema.hot_loop import (
    Command,
    CommandType,
    Response,
    ResponseStatus,
    Telemetry,
    calculate_state_hash,
)


def test_renderer_config_defaults():
    config = RendererConfig()
    assert config.mode == "cycles"
    assert config.max_samples == 128
    assert config.noise_threshold == 0.05


def test_board_config_validation():
    # Valid ChArUco
    cfg = BoardConfig(type="charuco", cols=5, rows=7, marker_size=0.03, square_size=0.04)
    assert cfg.marker_size == 0.03

    # Missing required for AprilGrid
    with pytest.raises(ValidationError):
        BoardConfig(type="aprilgrid", cols=5)  # type: ignore

    with pytest.raises(ValidationError, match="Unsupported board dictionary"):
        BoardConfig(
            type="aprilgrid",
            cols=2,
            rows=2,
            marker_size=0.03,
            spacing_ratio=0.2,
            dictionary="tagCircle21h7",
        )


def test_subject_config_rejects_unsupported_tag_family():
    with pytest.raises(ValidationError, match="Unsupported tag families"):
        TagSubjectConfig(tag_families=["tag36h11", "tagCircle21h7"])


def test_subject_config_rejects_unsupported_board_dictionary():
    with pytest.raises(ValidationError, match="Unsupported board dictionary"):
        BoardSubjectConfig(
            type="BOARD",
            cols=2,
            rows=2,
            marker_size_mm=30.0,
            spacing_ratio=0.2,
            dictionary="tagCircle21h7",
        )


def test_hot_loop_command_validation():
    # Valid
    cmd = Command(command_type=CommandType.INIT, request_id="123")
    assert cmd.request_id == "123"

    # Missing request_id
    with pytest.raises(ValidationError):
        Command(command_type=CommandType.INIT)  # type: ignore


def test_hot_loop_response_validation():
    resp = Response(status=ResponseStatus.SUCCESS, request_id="123")
    assert resp.status == ResponseStatus.SUCCESS


def test_telemetry_schema():
    tel = Telemetry(
        vram_used_mb=512.5,
        vram_total_mb=8192.0,
        cpu_usage_percent=15.0,
        state_hash="abc-123",
        uptime_seconds=100.0,
    )
    assert tel.vram_used_mb == 512.5


def test_state_hash_determinism():
    assets = ["a.exr", "b.png"]
    params = {"exposure": 1.0}
    h1 = calculate_state_hash(assets, params)
    h2 = calculate_state_hash(reversed(assets), params)
    assert h1 == h2
