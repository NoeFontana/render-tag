from pathlib import Path

import numpy as np

from render_tag.core.config import GenConfig
from render_tag.generation.scene import Generator


def test_generator_initializes_rng():
    """Verify that Generator initializes a numpy RNG in __init__."""
    config = GenConfig(version="0.1")
    output_dir = Path("/tmp/test_gen")
    seed = 1234

    gen = Generator(config, output_dir, global_seed=seed)

    # This should fail currently because Generator doesn't have an 'rng' attribute
    assert hasattr(gen, "rng")
    assert isinstance(gen.rng, np.random.Generator)

    # Verify it produces deterministic values
    val1 = gen.rng.uniform()

    # Re-initialize with same seed
    gen2 = Generator(config, output_dir, global_seed=seed)
    val2 = gen2.rng.uniform()

    assert val1 == val2
