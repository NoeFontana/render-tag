from render_tag.core.schema import SeedManager


def test_seed_manager_init():
    sm = SeedManager(42)
    assert sm.master_seed == 42


def test_shard_seeds_are_deterministic():
    sm1 = SeedManager(12345)
    seeds1 = [sm1.get_shard_seed(i) for i in range(5)]

    sm2 = SeedManager(12345)
    seeds2 = [sm2.get_shard_seed(i) for i in range(5)]

    assert seeds1 == seeds2
    assert len(set(seeds1)) == 5  # Ensure uniqueness


def test_shard_seeds_vary_with_master():
    sm1 = SeedManager(1)
    sm2 = SeedManager(2)

    assert sm1.get_shard_seed(0) != sm2.get_shard_seed(0)


def test_shard_seeds_vary_with_index():
    sm = SeedManager(42)
    assert sm.get_shard_seed(0) != sm.get_shard_seed(1)
