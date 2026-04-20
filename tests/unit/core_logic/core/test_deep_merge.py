"""Tests for ``core/merge.py``: deep_merge and merge_all."""

from __future__ import annotations

from render_tag.core.merge import deep_merge, merge_all


def test_dict_of_dicts_recurses():
    target = {"scene": {"lighting": {"intensity_min": 50.0}}}
    source = {"scene": {"lighting": {"intensity_max": 400.0}}}
    out = deep_merge(target, source)
    assert out["scene"]["lighting"] == {"intensity_min": 50.0, "intensity_max": 400.0}


def test_scalar_source_replaces():
    assert deep_merge({"fov": 60}, {"fov": 90}) == {"fov": 90}


def test_list_of_strings_concatenates_and_dedupes():
    target = {"scopes": ["DETECTION", "POSE_ACCURACY"]}
    source = {"scopes": ["DETECTION", "CALIBRATION"]}
    out = deep_merge(target, source)
    assert out["scopes"] == ["DETECTION", "POSE_ACCURACY", "CALIBRATION"]


def test_list_of_dicts_replaces_wholesale():
    target = {"cameras": [{"fov": 60}, {"fov": 90}]}
    source = {"cameras": [{"fov": 45}]}
    out = deep_merge(target, source)
    assert out["cameras"] == [{"fov": 45}]


def test_list_of_ints_replaces_wholesale():
    assert deep_merge({"res": [640, 480]}, {"res": [1920, 1080]})["res"] == [1920, 1080]


def test_none_source_replaces_target():
    assert deep_merge({"fov": 60}, {"fov": None}) == {"fov": None}


def test_missing_key_copied_from_source():
    assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_target_not_mutated():
    target = {"scene": {"lighting": {"intensity_min": 50.0}}}
    snapshot = {"scene": {"lighting": {"intensity_min": 50.0}}}
    deep_merge(target, {"scene": {"lighting": {"intensity_min": 200.0}}})
    assert target == snapshot


def test_merge_all_is_left_to_right():
    layers = [
        {"scene": {"lighting": {"intensity_min": 50.0, "intensity_max": 100.0}}},
        {"scene": {"lighting": {"intensity_max": 400.0}}},
        {"scene": {"lighting": {"intensity_min": 200.0}}},
    ]
    out = merge_all(layers)
    assert out["scene"]["lighting"] == {"intensity_min": 200.0, "intensity_max": 400.0}


def test_merge_all_empty_returns_empty():
    assert merge_all([]) == {}
