from render_tag.core.schema import ObjectRecipe, SceneRecipe, WorldRecipe
from render_tag.core.validator import RecipeValidator


def test_validator_detects_missing_hdri():
    """Verify validator catches missing HDRI background."""
    recipe = SceneRecipe(scene_id=0, world=WorldRecipe(background_hdri="nonexistent_studio.exr"))
    validator = RecipeValidator(recipe)
    validator._check_assets()
    assert any("HDRI" in e for e in validator.errors), "Should have reported missing HDRI"


def test_validator_detects_overlap():
    """Verify validator warns about overlapping tags."""
    # Two 10cm tags placed 5cm apart (Centers at 0.0 and 0.05)
    # They should overlap by 5cm.
    obj1 = ObjectRecipe(
        type="TAG",
        name="Tag_0",
        location=[0, 0, 0],
        rotation_euler=[0, 0, 0],
        scale=[1, 1, 1],
        properties={"tag_size": 0.1},
    )
    obj2 = ObjectRecipe(
        type="TAG",
        name="Tag_1",
        location=[0.05, 0, 0],
        rotation_euler=[0, 0, 0],
        scale=[1, 1, 1],
        properties={"tag_size": 0.1},
    )

    recipe = SceneRecipe(scene_id=0, objects=[obj1, obj2])
    validator = RecipeValidator(recipe)
    validator._check_geometry()

    assert any("Overlap" in w for w in validator.warnings), "Should have warned about overlap"


def test_validator_detects_missing_texture_path():
    """Verify validator catches missing background texture."""
    recipe = SceneRecipe(scene_id=0, world=WorldRecipe(texture_path="nonexistent_floor.png"))
    validator = RecipeValidator(recipe)
    validator._check_assets()
    assert any("texture" in e.lower() for e in validator.errors)


def test_validator_detects_outside_board():
    """Verify validator warns about tags outside board boundaries."""
    # 10cm board
    board = ObjectRecipe(
        type="BOARD",
        name="Board",
        location=[0, 0, 0],
        rotation_euler=[0, 0, 0],
        properties={"cols": 1, "rows": 1, "square_size": 0.1},
    )
    # 5cm tag at (0.1, 0) - clearly outside 10cm board centered at 0
    tag = ObjectRecipe(
        type="TAG",
        name="OutTag",
        location=[0.1, 0, 0],
        rotation_euler=[0, 0, 0],
        properties={"tag_size": 0.05},
    )

    recipe = SceneRecipe(scene_id=0, objects=[board, tag])
    validator = RecipeValidator(recipe)
    validator._check_geometry()

    assert any("outside board boundaries" in w for w in validator.warnings)
