import json
import sys
from pathlib import Path

import numpy as np

from render_tag.generation.projection_math import quaternion_xyzw_to_matrix


def main():
    dataset_dir = Path("output/dataset_01")
    rich_truth_path = dataset_dir / "rich_truth.json"
    job_spec_path = dataset_dir / "job_spec.json"

    if not rich_truth_path.exists():
        print(f"Error: {rich_truth_path} not found")
        sys.exit(1)

    with open(rich_truth_path) as f:
        detections = json.load(f)

    with open(job_spec_path) as f:
        job_spec = json.load(f)

    board_cfg = job_spec["scene_config"]["scenario"]["board"]

    b_type = board_cfg["type"]
    rows = board_cfg["rows"]
    cols = board_cfg["cols"]
    marker_size = board_cfg["marker_size"]

    if b_type == "aprilgrid":
        square_size = marker_size * (1.0 + board_cfg["spacing_ratio"])
    else:
        square_size = board_cfg["square_size"]

    board_width = cols * square_size
    board_height = rows * square_size

    image_id = detections[0]["image_id"]
    img_detections = [d for d in detections if d["image_id"] == image_id]

    pos = img_detections[0]["position"]
    quat_xyzw = img_detections[0]["rotation_quaternion"]

    print(f"Verifying {b_type} board: {cols}x{rows}")

    R_rel = quaternion_xyzw_to_matrix(quat_xyzw)
    t_rel = np.array(pos)

    with open(dataset_dir / "recipes_shard_0.json") as f:
        recipes = json.load(f)
    K = recipes[0]["cameras"][0]["intrinsics"]["k_matrix"]

    total_error = 0
    count = 0

    for det in img_detections:
        if det["record_type"] == "TAG":
            tag_id = det["tag_id"]
            if b_type == "aprilgrid":
                r_idx = tag_id // cols
                c_idx = tag_id % cols
            else:
                found = False
                tid = 0
                for r_idx in range(rows):
                    for c_idx in range(cols):
                        if (r_idx + c_idx) % 2 == 0:
                            if tid == tag_id:
                                found = True
                                break
                            tid += 1
                    if found:
                        break

            lx = -board_width / 2.0 + c_idx * square_size + square_size / 2.0
            ly = -board_height / 2.0 + r_idx * square_size + square_size / 2.0

            m = marker_size / 2.0
            local_corners = np.array(
                [
                    [lx - m, ly + m, 0.0],
                    [lx + m, ly + m, 0.0],
                    [lx + m, ly - m, 0.0],
                    [lx - m, ly - m, 0.0],
                ]
            )

            p_cam = (R_rel @ local_corners.T).T + t_rel

            fx, fy = K[0][0], K[1][1]
            cx, cy = K[0][2], K[1][2]

            pred_pixels = np.zeros((4, 2))
            pred_pixels[:, 0] = (p_cam[:, 0] * fx / p_cam[:, 2]) + cx
            pred_pixels[:, 1] = (p_cam[:, 1] * fy / p_cam[:, 2]) + cy

            actual_pixels = np.array(det["corners"])
            err = np.sqrt(np.sum((pred_pixels - actual_pixels) ** 2, axis=1))
            total_error += np.sum(err)
            count += len(err)

        elif det["record_type"] == "APRILGRID_CORNER":
            r_idx = det["tag_id"] // 100
            c_idx = det["tag_id"] % 100

            lx = -board_width / 2.0 + c_idx * square_size
            ly = -board_height / 2.0 + r_idx * square_size

            p_cam = (R_rel @ np.array([lx, ly, 0.0])) + t_rel

            fx, fy = K[0][0], K[1][1]
            cx, cy = K[0][2], K[1][2]

            px = (p_cam[0] * fx / p_cam[2]) + cx
            py = (p_cam[1] * fy / p_cam[2]) + cy

            actual = np.array(det["corners"][0])
            err = np.sqrt(np.sum((np.array([px, py]) - actual) ** 2))
            total_error += err
            count += 1

    if count > 0:
        avg_err = total_error / count
        print(f"Mean Projection Error: {avg_err:.6f} px")
        if avg_err < 0.1:
            print("PASS: Sub-pixel accuracy verified.")
        else:
            print("FAIL: Projection error too high!")
            sys.exit(1)
    else:
        print("No keypoints found to verify.")


if __name__ == "__main__":
    main()
