"""
Unit tests for compositor.py using mocked Blender environment.
"""

from render_tag.scripts.compositor import compose_scene


def test_compose_scene_plain_counting(mock_blender_environment):
    """Verify tag count calculation for plain layout."""
    # Configs
    tag_config = {"size_meters": 0.1, "tags_per_scene": [5, 5]}
    scenario_config = {"layout": "plain"}
    scene_config = {}
    physics_config = {"drop_height": 0.1}
    tag_families = ["tag36h11"]

    # Run
    tag_objects, _layout_objects, mode = compose_scene(
        scene_idx=0,
        tag_config=tag_config,
        scenario_config=scenario_config,
        scene_config=scene_config,
        physics_config=physics_config,
        tag_families=tag_families,
    )

    # Assertions
    assert mode == "plain"
    assert len(tag_objects) == 5
    # Verify objects are our MockObjects (because of global key)
    assert tag_objects[0].blender_obj["tag_family"] == "tag36h11"


def test_compose_scene_charuco_grid(mock_blender_environment):
    """Verify ChArUco grid math."""
    # 4x4 grid -> 16 squares.
    # Checkerboard: approx half are white (tag slots).
    # 16 / 2 = 8.
    # Ceil((16+1)/2) actually for starting with white.
    # 4*4=16. (16+1)//2 = 8.

    tag_config = {"grid_size": [4, 4], "size_meters": 0.1}
    scenario_config = {"layout": "cb"}
    scene_config = {}
    physics_config = {}
    tag_families = ["tag36h11"]

    tag_objects, layout_objects, mode = compose_scene(
        0, tag_config, scenario_config, scene_config, physics_config, tag_families
    )

    assert mode == "cb"
    assert len(tag_objects) == 8

    # Check layout object count (board + squares)
    # Board is 1 object.
    # Squares? create_board creates 1 board object.
    # But apply_layout might add squares if "cb"?
    # Wait, create_board creates the mesh.
    # apply_layout doesn't create surrounding squares for board layouts usually, unless needed.
    # Let's check logic:
    # "Create board if needed ... board = create_board(...)"
    # layout_objects should have at least the board.
    # apply_layout for "cb" positions tags.
    assert len(layout_objects) >= 1


def test_compose_scene_aprilgrid(mock_blender_environment):
    """Verify AprilGrid (full grid) count."""
    tag_config = {"grid_size": [3, 2]}  # 6 tags
    scenario_config = {"layout": "aprilgrid"}
    scene_config = {}
    physics_config = {}
    tag_families = ["tag36h11"]

    tag_objects, _layout_objects, mode = compose_scene(
        0, tag_config, scenario_config, scene_config, physics_config, tag_families
    )

    assert mode == "aprilgrid"
    assert len(tag_objects) == 6
