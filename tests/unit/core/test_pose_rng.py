import numpy as np

from render_tag.generation.camera import sample_camera_pose


def test_sample_camera_pose_is_deterministic_with_rng():
    """Verify that sample_camera_pose produces identical results with same RNG state."""
    look_at = np.array([0, 0, 0])
    seed = 42
    
    rng1 = np.random.default_rng(seed)
    pose1 = sample_camera_pose(look_at, rng=rng1)
    
    rng2 = np.random.default_rng(seed)
    pose2 = sample_camera_pose(look_at, rng=rng2)
    
    np.testing.assert_array_almost_equal(pose1.location, pose2.location)
    np.testing.assert_array_almost_equal(pose1.transform_matrix, pose2.transform_matrix)

def test_sample_camera_pose_evolves_rng():
    """Verify that sample_camera_pose advances the RNG state."""
    look_at = np.array([0, 0, 0])
    rng = np.random.default_rng(42)
    
    pose1 = sample_camera_pose(look_at, rng=rng)
    pose2 = sample_camera_pose(look_at, rng=rng)
    
    # Locations should be different
    assert not np.array_equal(pose1.location, pose2.location)
