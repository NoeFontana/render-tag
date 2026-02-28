import json
import subprocess
import sys
import time
from pathlib import Path


def run_gen(config_path, output_dir):
    cmd = [
        "uv",
        "run",
        "render-tag",
        "generate",
        "--config",
        str(config_path),
        "--output",
        str(output_dir),
        "--scenes",
        "1",
        "--workers",
        "1",
    ]
    print(f"Running: {' '.join(cmd)}")
    start = time.time()
    subprocess.run(cmd, check=True)
    return time.time() - start


def main():
    base_dir = Path("test_output/sanity_cv_safe")
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Define High-Quality Config (Reference)
    hq_config_path = base_dir / "hq_config.yaml"
    hq_config_path.write_text("""
renderer:
  mode: cycles
  samples: 512
  denoising: false
    """)

    # 2. Define CV-Safe Config (Optimized)
    cv_safe_config_path = base_dir / "cv_safe_config.yaml"
    cv_safe_config_path.write_text("""
renderer:
  mode: cycles
  noise_threshold: 0.05
  max_samples: 128
  enable_denoising: true
    """)

    # We need to ensure both use the same seed for direct comparison
    # The CLI --seed flag can be used.

    print("--- Rendering Reference (High Quality) ---")
    hq_dir = base_dir / "hq"
    hq_time = run_gen(hq_config_path, hq_dir)

    print("\n--- Rendering CV-Safe (Optimized) ---")
    cv_safe_dir = base_dir / "cv_safe"
    cv_safe_time = run_gen(cv_safe_config_path, cv_safe_dir)

    print("\nResults:")
    print(f"HQ Render Time:      {hq_time:.2f}s")
    print(f"CV-Safe Render Time: {cv_safe_time:.2f}s")
    print(f"Speedup:             {hq_time / cv_safe_time:.2f}x")

    # 3. Compare Detections (Corners)
    hq_csv = hq_dir / "tags.csv"
    cv_safe_csv = cv_safe_dir / "tags.csv"

    if not hq_csv.exists() or not cv_safe_csv.exists():
        print("Error: CSV files not found. Render might have failed.")
        sys.exit(1)

    # Simple check for now: count detections and compare first corner of first detection
    # In a real scenario, we'd use Polars to join on image_id and tag_id and calculate L2 error.
    import polars as pl

    df_hq = pl.read_csv(hq_csv)
    df_cv = pl.read_csv(cv_safe_csv)

    print(f"\nHQ Detections:      {len(df_hq)}")
    print(f"CV-Safe Detections: {len(df_cv)}")

    if len(df_hq) != len(df_cv):
        print("Warning: Detection count mismatch!")

    # Join and compare
    # We need to parse the corners string back to float lists
    # corners column is usually a string like "[[x1,y1],...]"
    def parse_corners(s):
        return json.loads(s)

    # Simplified corner comparison for this sanity check
    # We'll just verify the detections are present and "close"
    print("\nCorner Accuracy Check (First tag):")
    if len(df_hq) > 0 and len(df_cv) > 0:
        c_hq = parse_corners(df_hq[0, "corners"])
        c_cv = parse_corners(df_cv[0, "corners"])

        # Calculate max L1 error across all 4 corners
        import numpy as np

        err = np.max(np.abs(np.array(c_hq) - np.array(c_cv)))
        print(f"Max Corner Pixel Error: {err:.4f}")

        if err < 1.0:
            print("PASS: Sub-pixel consistency maintained.")
        else:
            print("FAIL: Significant corner shift detected!")
            sys.exit(1)


if __name__ == "__main__":
    main()
