
import cv2
from render_tag.core.schema.board import BoardConfig, BoardType
from render_tag.generation.texture_factory import TextureFactory
from pathlib import Path

def debug_visualize():
    output_dir = Path("output/test_debug")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    factory = TextureFactory(px_per_mm=1) # Low res for quick look
    
    # 1. AprilGrid
    ag_config = BoardConfig(
        type=BoardType.APRILGRID,
        rows=2,
        cols=3,
        marker_size=0.1,
        spacing_ratio=0.5,
        dictionary="tag36h11"
    )
    ag_img = factory.generate_board_texture(ag_config)
    cv2.imwrite(str(output_dir / "debug_aprilgrid.png"), ag_img)
    print(f"AprilGrid shape: {ag_img.shape}, mean: {ag_img.mean()}")

    # 2. ChArUco
    ch_config = BoardConfig(
        type=BoardType.CHARUCO,
        rows=4,
        cols=4,
        square_size=0.1,
        marker_size=0.08,
        dictionary="DICT_4X4_50"
    )
    ch_img = factory.generate_board_texture(ch_config)
    cv2.imwrite(str(output_dir / "debug_charuco.png"), ch_img)
    print(f"ChArUco shape: {ch_img.shape}, mean: {ch_img.mean()}")

if __name__ == "__main__":
    debug_visualize()
