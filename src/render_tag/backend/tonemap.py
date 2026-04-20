"""Post-render tone-mapping operators.

Blender's default view transform is Filmic, so rendered frames arrive at this
module already filmic-tonemapped. ``filmic`` is the passthrough baseline;
``srgb`` / ``linear`` are measurable deviations from it. Curves are
approximations chosen to make the ``tone_mapping`` field observable in
characterization sweeps, not an OCIO-correct pipeline.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

ToneMappingMode = Literal["linear", "srgb", "filmic"]

_FILMIC_INVERSE_GAMMA = 2.4
_SRGB_GAMMA = 2.2


def apply_tone_mapping(image: np.ndarray, mode: ToneMappingMode) -> np.ndarray:
    """Apply a post-render tone-mapping operator.

    - ``filmic``: identity. Input is already Blender-filmic from the render call.
    - ``linear``: strip filmic via gamma-2.4 inverse, yielding a scene-linear-ish estimate.
    - ``srgb``: strip filmic, then re-encode with sRGB's ~gamma 2.2.
    """
    if mode == "filmic":
        return image

    dtype = image.dtype
    if dtype == np.uint8:
        img_float = image.astype(np.float32) / 255.0
    elif dtype == np.float32:
        img_float = image
    else:
        img_float = image.astype(np.float32)
    img_float = np.clip(img_float, 0.0, 1.0)

    linear = np.power(img_float, _FILMIC_INVERSE_GAMMA)

    if mode == "linear":
        result = linear
    elif mode == "srgb":
        result = np.power(linear, 1.0 / _SRGB_GAMMA)
    else:
        raise ValueError(f"Unknown tone_mapping mode: {mode!r}")

    result = np.clip(result, 0.0, 1.0)
    if dtype == np.uint8:
        return np.round(result * 255.0).astype(np.uint8)
    return result.astype(dtype)
