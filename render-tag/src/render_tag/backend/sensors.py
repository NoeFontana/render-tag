import numpy as np
from render_tag.schema import SensorNoiseConfig, NoiseType

def apply_parametric_noise(image: np.ndarray, config: SensorNoiseConfig) -> np.ndarray:
    """Apply parametric sensor noise to the image.
    
    Args:
        image: Input RGB image array (0-255).
        config: SensorNoiseConfig object with noise parameters.
        
    Returns:
        Noisy RGB image array (0-255).
    """
    img_float = image.astype(np.float32) / 255.0
    noisy = img_float.copy()
    
    if config.model == NoiseType.GAUSSIAN:
        if config.stddev > 0:
            noise = np.random.normal(config.mean, config.stddev, img_float.shape)
            noisy = img_float + noise
        
    elif config.model == NoiseType.POISSON:
        # Simulate Poisson noise (shot noise)
        # We need to scale the image up to represent photon counts
        # A simple approximation is to use a scale factor (simulating gain/exposure)
        # If no explicit scale is provided, we assume a standard range
        scale = 1000.0  # Arbitrary scale factor for photon count simulation
        noisy = np.random.poisson(img_float * scale) / scale
        
    elif config.model == NoiseType.SALT_AND_PEPPER:
        if config.amount > 0:
            # Generate random mask
            # Note: This is a simplified S&P implementation applied per channel
            # For strict S&P it should likely apply to all channels at same pixel
            
            # Total pixels to affect
            num_pixels = int(config.amount * image.size)
            
            # Salt (White)
            num_salt = int(num_pixels * config.salt_vs_pepper)
            if num_salt > 0:
                coords_salt = [np.random.randint(0, i - 1, num_salt) for i in image.shape]
                noisy[tuple(coords_salt)] = 1.0

            # Pepper (Black)
            num_pepper = num_pixels - num_salt
            if num_pepper > 0:
                coords_pepper = [np.random.randint(0, i - 1, num_pepper) for i in image.shape]
                noisy[tuple(coords_pepper)] = 0.0

    noisy = np.clip(noisy, 0, 1)
    return (noisy * 255).astype(np.uint8)
