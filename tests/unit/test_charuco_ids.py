import pytest
from render_tag.generation.board import BoardSpec, BoardType, compute_charuco_layout

def test_charuco_id_assignment_standard():
    """
    Test that ChArUco layout assigns IDs according to OpenCV standard
    (which is NOT always sequential 0,1,2,3 for all white squares).
    Wait, actually OpenCV ChArUcoBoard assigns ArUco marker IDs to 
    the white squares. 
    The current implementation just does sequential 0,1,2...
    
    If we want parity, we should be able to pass specific IDs or 
    ensure the default matches OpenCV's logic.
    """
    spec = BoardSpec(rows=4, cols=4, square_size=0.1)
    
    # 4x4 board has 8 white squares (tags)
    layout = compute_charuco_layout(spec)
    
    ids = [sq.tag_id for sq in layout.squares if sq.has_tag]
    
    # Current implementation yields [0, 1, 2, 3, 4, 5, 6, 7]
    # In OpenCV, they are also usually sequential but we want to 
    # allow providing specific IDs for complex dictionaries or randomized boards.
    
    assert len(ids) == 8
    assert ids == [0, 1, 2, 3, 4, 5, 6, 7]

def test_charuco_custom_ids():
    """
    Test that ChArUco layout respects a provided list of tag IDs.
    """
    spec = BoardSpec(rows=2, cols=2, square_size=0.1)
    # 2x2 board has 2 white squares: (0,0) and (1,1)
    tag_ids = [42, 99]
    
    layout = compute_charuco_layout(spec, tag_ids=tag_ids)
    
    ids = [sq.tag_id for sq in layout.squares if sq.has_tag]
    assert ids == [42, 99]
    
    # Verify ValueError on wrong length
    with pytest.raises(ValueError, match="Expected 2 tag IDs, got 3"):
        compute_charuco_layout(spec, tag_ids=[1, 2, 3])
