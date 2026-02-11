"""
Unit tests for the backend executor.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from render_tag.backend.executor import parse_args


def test_parse_args() -> None:
    with patch("sys.argv", ["executor.py", "--recipe", "rec.json", "--output", "out"]):
        args = parse_args()
        assert args.recipe == Path("rec.json")
        assert args.output == Path("out")
        assert args.renderer_mode == "cycles"


@patch("render_tag.backend.executor.execute_recipe")
@patch("render_tag.backend.executor.json.load")
@patch("render_tag.backend.executor.open")
@patch("render_tag.backend.executor.CSVWriter")
@patch("render_tag.backend.executor.COCOWriter")
@patch("render_tag.backend.executor.RichTruthWriter")
@patch("render_tag.backend.executor.SidecarWriter")
@patch("render_tag.backend.executor.bproc")
@patch("render_tag.backend.executor.parse_args")
def test_main(
    mock_parse,
    mock_bproc,
    mock_sidecar,
    mock_rich,
    mock_coco,
    mock_csv,
    mock_open,
    mock_load,
    mock_execute,
    tmp_path: Path,
) -> None:
    from render_tag.backend.executor import main

    mock_parse.return_value = MagicMock(
        recipe=Path("recipe.json"),
        output=tmp_path,
        renderer_mode="cycles",
        shard_id="0",
    )
    mock_load.return_value = [{"scene_id": "1"}]

    main()

    assert mock_bproc.init.called
    assert mock_execute.called
    assert mock_coco().save.called
    assert mock_rich().save.called
