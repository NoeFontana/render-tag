import numpy as np

# Constants matching NoiseType enum
NOISE_TYPE_GAUSSIAN = "gaussian"
NOISE_TYPE_POISSON = "poisson"
NOISE_TYPE_SALT_AND_PEPPER = "salt_and_pepper"

def apply_parametric_noise(image: np.ndarray, config: dict) -> np.ndarray:
    """Apply parametric sensor noise to the image.
    
    Args:
        image: Input RGB image array (0-255).
        config: Dictionary containing noise parameters (from SensorNoiseConfig).
        
    Returns:
        Noisy RGB image array (0-255).
    """
    img_float = image.astype(np.float32) / 255.0
    noisy = img_float.copy()
    
    model = config.get("model", NOISE_TYPE_GAUSSIAN)
    
    if model == NOISE_TYPE_GAUSSIAN:
        mean = config.get("mean", 0.0)
        stddev = config.get("stddev", 0.0)
        if stddev > 0:
            noise = np.random.normal(mean, stddev, img_float.shape)
            noisy = img_float + noise
        
    elif model == NOISE_TYPE_POISSON:
        # Simulate Poisson noise (shot noise)
        scale = 1000.0  # Arbitrary scale factor for photon count simulation
        noisy = np.random.poisson(img_float * scale) / scale
        
    elif model == NOISE_TYPE_SALT_AND_PEPPER:
        amount = config.get("amount", 0.0)
        salt_vs_pepper = config.get("salt_vs_pepper", 0.5)
        
        if amount > 0:
            # Generate random mask
            # Total pixels to affect
            num_pixels = int(amount * image.size)
            
            # Salt (White)
            num_salt = int(num_pixels * salt_vs_pepper)
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