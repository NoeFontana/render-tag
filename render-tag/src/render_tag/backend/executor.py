import sys
import argparse
import json
import logging
from pathlib import Path

# Move site-packages to the end
sys.path = [p for p in sys.path if "site-packages" not in p] + [
    p for p in sys.path if "site-packages" in p
]

import blenderproc as bproc

# Add the src directory to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from render_tag.backend.render_loop import execute_recipe
from render_tag.data_io.writers import (
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)
from render_tag.tools.benchmarking import Benchmarker

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BlenderProc render-tag executor")
    parser.add_argument("--recipe", type=Path, required=True, help="Path to scene_recipes.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--renderer-mode", choices=["cycles", "workbench", "eevee"], default="cycles")
    parser.add_argument("--shard-id", type=str, default="main", help="Unique ID for output files")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    benchmarker = Benchmarker(session_name=f"Shard_{args.shard_id}")

    with benchmarker.measure("Blender_Init"):
        with open(args.recipe) as f:
            recipes = json.load(f)
        bproc.init()
        bproc.clean_up()

    csv_writer = CSVWriter(output_dir / f"tags_shard_{args.shard_id}.csv")
    coco_writer = COCOWriter(output_dir)
    rich_writer = RichTruthWriter(output_dir / "rich_truth.json")
    sidecar_writer = SidecarWriter(output_dir)

    with benchmarker.measure("Total_Execution"):
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

    with benchmarker.measure("Save_Results"):
        coco_writer.save()
        rich_writer.save()

    benchmarker.report.log_summary()

if __name__ == "__main__":
    main()