"""Sensor dynamic-range emulation.

Applied in the render pipeline BEFORE tone mapping — dynamic range is a capture-
stage property of the sensor, not an ISP effect. A lower `dynamic_range_db`
raises the noise floor (dark pixels cannot drop below it) and saturates the
highlight ceiling. This models the shadow-crush and highlight-clip that make
low-DR industrial sensors fail where cinema sensors recover.

The conversion `stops = db / 6.02` is the standard 20*log10(2) relation between
dB and photographic stops.
"""

from __future__ import annotations

import numpy as np

_DB_PER_STOP = 6.02


def apply_sensor_dr(image: np.ndarray, dr_db: float | None) -> np.ndarray:
    """Clamp an image into a sensor's usable [floor, 1.0] range.

    ``None`` (or non-positive dB) is a no-op. At 120 dB the floor is below
    1e-6 which is effectively transparent; low-DR values like 60 dB raise the
    floor to ~1e-3 of full scale, measurably crushing shadows.
    """
    if dr_db is None or dr_db <= 0.0:
        return image

    stops = float(dr_db) / _DB_PER_STOP
    floor_norm = float(2.0 ** (-stops))

    dtype = image.dtype
    if dtype == np.uint8:
        img_float = image.astype(np.float32) / 255.0
    elif dtype == np.float32:
        img_float = image
    else:
        img_float = image.astype(np.float32)

    clipped = np.clip(img_float, floor_norm, 1.0)

    if dtype == np.uint8:
        return np.round(clipped * 255.0).astype(np.uint8)
    return clipped.astype(dtype)
