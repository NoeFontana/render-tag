# render-tag Documentation

Welcome to the official documentation for `render-tag`, a high-performance procedural 3D synthetic data generator for fiducial marker training.

`render-tag` is designed to bridge the gap between photorealistic 3D rendering and high-precision computer vision requirements, specifically for AprilTag and ArUco detection.

## Core Documentation

-   **[User Guide](guide.md)**: Installation, CLI usage, and configuration presets.
-   **[Architecture](architecture.md)**: Deep dive into the Host-Backend design and "Hot Loop" implementation.
-   **[Coordinate Systems & Standards](coordinates.md)**: Canonical geometric contracts, pose conventions, and output data formats.
-   **[Benchmarking & Auditing](benchmarking.md)**: Tracking performance and verifying dataset quality.
-   **[API Reference](api.md)**: Low-level Python API documentation.

## Key Features

-   **Procedural Scene Generation**: Deterministic generation of complex 3D scenes with randomized lighting, textures, and physics.
-   **Host-Backend Architecture**: Decouples heavy 3D rendering (Blender) from generation logic (Python), enabling high-throughput pipelines.
-   **Sub-pixel Accuracy**: Optimized Cycles rendering configurations ensuring edge and corner integrity.
-   **Rich Annotations**: Comprehensive ground truth including 6DoF poses, PPM, and visibility metrics.
-   **Hugging Face Integration**: Native support for managing assets and datasets on the Hub.
