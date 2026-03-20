"""
Sensor noise simulation strategies for render-tag.

Provides a pluggable Strategy Pattern architecture for applying various
parametric noise models to rendered images.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from render_tag.core.schema.recipe import SensorNoiseConfig

import numpy as np

from render_tag.core.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class NoiseStrategy(Protocol):
    """Protocol for noise application strategies."""

    def apply(self, image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
        """
        Apply a specific noise model to the input image.

        Args:
            image: Input RGB image array (float32, 0.0-1.0 preferred for processing).
            config: Configuration for the noise model.

        Returns:
            Noisy RGB image array (float32, 0.0-1.0).
        """
        ...


class GaussianNoiseStrategy:
    """Applies additive Gaussian noise."""

    def apply(self, image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
        mean = config.mean
        stddev = config.stddev
        seed = config.seed
        rng = np.random.default_rng(seed)

        # Standard Engineer: Use np.asarray to safely handle mocks in test environments
        if np.asarray(stddev).any() and np.asarray(stddev) > 0:
            noise = rng.normal(mean, stddev, image.shape)
            return image + noise
        return image


class PoissonNoiseStrategy:
    """Applies shot noise using a Poisson distribution."""

    def apply(self, image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
        # Note: Poisson model currently uses 'amount' as scale or defaults to 1000.0
        # for historical compatibility if we don't have a dedicated scale field.
        scale = getattr(config, "amount", 1000.0)
        seed = config.seed
        rng = np.random.default_rng(seed)
        return rng.poisson(image * scale) / scale


class SaltAndPepperNoiseStrategy:
    """Applies impulsive salt and pepper noise."""

    def apply(self, image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
        amount = config.amount
        salt_vs_pepper = config.salt_vs_pepper
        seed = config.seed
        rng = np.random.default_rng(seed)

        noisy = image.copy()
        if np.asarray(amount).any() and np.asarray(amount) > 0:
            num_pixels = int(np.asarray(amount) * image.size)

            # Salt (White)
            num_salt = int(num_pixels * salt_vs_pepper)
            if num_salt > 0:
                coords_salt = [rng.integers(0, i, size=num_salt) for i in image.shape]
                noisy[tuple(coords_salt)] = 1.0

            # Pepper (Black)
            num_pepper = num_pixels - num_salt
            if num_pepper > 0:
                coords_pepper = [rng.integers(0, i, size=num_pepper) for i in image.shape]
                noisy[tuple(coords_pepper)] = 0.0
        return noisy


class NoiseEngine:
    """Registry and executor for noise strategies."""

    def __init__(self):
        self._strategies: dict[str, NoiseStrategy] = {
            "gaussian": GaussianNoiseStrategy(),
            "poisson": PoissonNoiseStrategy(),
            "salt_and_pepper": SaltAndPepperNoiseStrategy(),
        }

    def apply_noise(self, image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
        """Dispatcher that selects and runs the appropriate strategy."""
        model_type = config.model
        strategy = self._strategies.get(model_type)

        # 1. Convert to float for processing
        img_float = image.astype(np.float32) / 255.0

        if not strategy:
            logger.warning(f"Unknown noise model '{model_type}'. Skipping noise.")
            result = img_float
        else:
            result = strategy.apply(img_float, config)

        # 2. Finalize: Clip and convert back to uint8
        result = np.clip(result, 0, 1)
        return np.round(np.asarray(result) * 255).astype(np.uint8)


# Global engine instance for easy access
_engine = NoiseEngine()


def apply_parametric_noise(image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
    """Legacy entry point that delegates to the NoiseEngine."""
    return _engine.apply_noise(image, config)
