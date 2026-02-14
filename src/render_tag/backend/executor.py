import blenderproc as bproc
import logging
import sys
from pathlib import Path

# 1. BOOTSTRAP: Synchronize environment first
try:
    _src_path = str(Path(__file__).resolve().parents[2])
    if _src_path not in sys.path:
        sys.path.insert(0, _src_path)
    from render_tag.backend import bootstrap

    bootstrap.setup_environment()
except Exception as e:
    sys.stderr.write(f"BOOTSTRAP FAILED: {e}\n")

"""
Minimal one-shot executor for render-tag.
Acts as a wrapper around render_loop for non-ZMQ contexts (e.g. Docker).
"""

import argparse  # noqa: E402
import json  # noqa: E402

from render_tag.backend.engine import execute_recipe  # noqa: E402
from render_tag.data_io.writers import (  # noqa: E402
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--renderer-mode", choices=["cycles", "workbench", "eevee"], default="cycles"
    )
    parser.add_argument("--shard-id", type=str, default="main")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    bproc.init()
    bproc.clean_up()

    csv_writer = CSVWriter(output_dir / f"tags_shard_{args.shard_id}.csv")
    coco_writer = COCOWriter(output_dir, filename=f"coco_shard_{args.shard_id}.json")
    rich_writer = RichTruthWriter(output_dir / "rich_truth.json")
    sidecar_writer = SidecarWriter(output_dir)

    with open(args.recipe) as f:
        recipes = json.load(f)

    for recipe in recipes:
        execute_recipe(
            recipe,
            output_dir,
            args.renderer_mode,
            csv_writer,
            coco_writer,
            rich_writer,
            sidecar_writer,
        )

    coco_writer.save()
    rich_writer.save()


if __name__ == "__main__":
    main()
