"""
Sensor noise simulation strategies for render-tag.

Provides a pluggable Strategy Pattern architecture for applying various
parametric noise models to rendered images.
"""

from typing import Protocol, runtime_checkable

import numpy as np

from render_tag.core.logging import get_logger
from render_tag.core.schema import SensorNoiseComponent, SensorNoiseConfig

logger = get_logger(__name__)


@runtime_checkable
class NoiseStrategy(Protocol):
    """Protocol for noise application strategies."""

    def apply(
        self, image: np.ndarray, config: SensorNoiseConfig | SensorNoiseComponent
    ) -> np.ndarray:
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

    def apply(
        self, image: np.ndarray, config: SensorNoiseConfig | SensorNoiseComponent
    ) -> np.ndarray:
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

    def apply(
        self, image: np.ndarray, config: SensorNoiseConfig | SensorNoiseComponent
    ) -> np.ndarray:
        scale = float(getattr(config, "scale", 1000.0))
        seed = config.seed
        rng = np.random.default_rng(seed)
        return rng.poisson(image * scale) / scale


class SaltAndPepperNoiseStrategy:
    """Applies impulsive salt and pepper noise."""

    def apply(
        self, image: np.ndarray, config: SensorNoiseConfig | SensorNoiseComponent
    ) -> np.ndarray:
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
        """Dispatcher that selects and runs the appropriate strategy.

        If ``config.models`` is populated, each component is applied in order
        (stacked pipeline). Otherwise the flat fields are treated as a single-
        component legacy config.
        """
        # 1. Convert to float for processing
        img_float = image.astype(np.float32) / 255.0

        components = self._resolve_components(config)
        result = img_float
        for comp in components:
            strategy = self._strategies.get(comp.model)
            if not strategy:
                logger.warning(f"Unknown noise model '{comp.model}'. Skipping component.")
                continue
            result = strategy.apply(result, comp)

        # 2. Finalize: Clip and convert back to uint8
        result = np.clip(result, 0, 1)
        return np.round(np.asarray(result) * 255).astype(np.uint8)

    @staticmethod
    def _resolve_components(
        config: SensorNoiseConfig,
    ) -> list[SensorNoiseConfig | SensorNoiseComponent]:
        """Return the list of noise components to apply.

        When ``config.models`` is set, each component inherits the parent's
        seed if it doesn't declare its own — that keeps stacked pipelines
        deterministic by default while allowing per-layer seed overrides.
        """
        if not config.models:
            return [config]

        resolved: list[SensorNoiseConfig | SensorNoiseComponent] = []
        for idx, comp in enumerate(config.models):
            if comp.seed is None and config.seed is not None:
                comp = comp.model_copy(update={"seed": config.seed + idx})
            resolved.append(comp)
        return resolved


# Global engine instance for easy access
_engine = NoiseEngine()


def apply_parametric_noise(image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
    """Legacy entry point that delegates to the NoiseEngine."""
    return _engine.apply_noise(image, config)
