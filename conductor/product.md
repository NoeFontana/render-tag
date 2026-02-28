# Initial Concept
Procedural 3D data generation for AprilTag training (Offline).

# Product Definition

## Target Users
- **Computer Vision Researchers:** Utilizing synthetic datasets to train, fine-tune, and validate tag detection and localization models.
- **Robotics Engineers:** Benchmarking tag tracking performance and visual odometry in simulated environments that mimic real-world deployment.
- **Infrastructure Engineers:** Managing large-scale data generation pipelines with managed binary assets and hermetic reproducibility.
- **MLOps Engineers:** Streamlining dataset versioning and distribution through cloud-based asset repositories.
- **Benchmark Architects:** Defining strict Data APIs and declarative manifests for systematic performance evaluation.
- **Perception Engineers:** Validating calibration algorithms and corner refinement accuracy against mathematically perfect ground truth.

## Core Goals & Features
- **High-Fidelity Rendering:** Generate photorealistic scenes with complex lighting, varied textures, and realistic shadows to minimize the sim-to-real gap.
- **CV-Safe Rendering Strategy:** Intelligent adaptive sampling, guided denoising (Albedo/Normal), and min-max light bounce optimization that maximizes throughput while preserving sub-pixel corner accuracy and essential specular highlights for detector training.
- **Sensor Simulation:** Accurately model camera sensor characteristics, including noise profiles, lens distortion, motion blur, and rolling shutter artifacts.
- **Automated Annotations:** Produce pixel-perfect ground-truth data, including 2D/3D bounding boxes, segmentation masks, and standard formats like COCO. Enforces strict geometric contracts (OpenCV convention: Y-down, Clockwise) for all projected keypoints using a 3D-anchored orientation pipeline.
- **Tag-Driven Automated Release Pipeline:** Immutable artifact generation triggered by semantic Git tags. Automatically compiles Python host assets, builds multi-tagged Docker images with provenance attestation, and publishes formal GitHub Releases with integrated changelogs from Git notes.
- **Polymorphic Subject Architecture:** Agnostic rendering pipeline that treats all subjects (Tags, Calibration Boards) as generic primitives. Shifts domain-specific logic to the Host, enabling rapid support for new subject types without modifying the core renderer.
- **Strategy-Patterned Generation:** Decoupled compilation loop that utilizes interchangeable "Subject Strategies" to orchestrate asset preparation and pose sampling, ensuring maximum architectural flexibility and extensibility.
- **Immutable Job Specs & Strict Versioning:** Cryptographically verifiable "Unit of Work" definitions with mandatory schema versioning (v0.2+). Supports polymorphic subject definitions with explicit type discriminators.
- **Dataset Auditing & CI/CD Integrity:** Integrated "Contract of Trust" validation to verify geometric coverage (incidence angles, distances), environmental variance, and data integrity via automated Quality Gates. Automated GitHub Actions CI/CD pipeline enforces formatting, linting, architectural boundaries, and regression testing on every pull request.
- **High-Fidelity Calibration Targets:** Mathematically perfect targets (ChArUco, AprilGrid) using Bit-Perfect Texture Synthesis and a Single-Plane Architecture to eliminate geometric drift and Z-fighting. Synchronizes 3D board geometry with CV-standard 2D pixel coordinates (Top-Left origin, Y-Down), ensuring sub-pixel accurate keypoint export with strict row-major, zero-indexed topology for seamless OpenCV and Kalibr integration.
- **Pose Estimation Baseline:** Systematic sweeps (distance, angle) with high-precision quaternion ground truth for absolute pose verification. Anchors 2D corner ordering to 3D local-space keypoints to guarantee orientation integrity across all poses.
- **PPM-Driven Generation:** Goal-oriented visual resolution targets (Pixels Per Module) that linearize dataset difficulty and ensure uniform coverage across detection scenarios.
- **Managed Assets:** Single Source of Truth (SSoT) for HDRIs, textures, and models via Hugging Face, ensuring zero-config onboarding and deterministic results across environments.

## Supported Environments
- **Controlled Indoor:** Lab and office settings with consistent lighting for baseline testing.
- **Dynamic Outdoor/Industrial:** Complex environments with varied lighting, weather effects, and potential occlusions for robustness testing.
- **Abstract/Geometric:** Minimalist scenes focused on isolating variables like tag geometry and visibility.

## User Interaction
- **CLI-First Workflow:** A robust Command Line Interface designed for batch generation and seamless integration into automated pipelines.
- **Config-Driven Experiments:** Flexible YAML or JSON configuration files for defining parameters, scene distributions, and experiment variations.

## Performance & Scalability
- **Distributed Sharding:** Architecture supports horizontal scaling and sharding across multiple GPUs or compute nodes.
- **Pluggable Execution:** Support for multiple rendering backends, including local subprocesses and hermetic Docker containers, enabling seamless transition from development to high-performance computing (HPC) environments.
- **Environment Synchronization:** Robust bootstrap pattern ensures that the rendering backend (Blender) perfectly matches the host's virtual environment dependencies, eliminating sim-to-sim parity issues.
- **Hot Loop Optimization:** Scene recycling and persistent data management in the rendering backend, minimizing initialization overhead and maximizing throughput for batch generation.
- **Smart Resumption:** Deterministic shard-level validation and aggressive file cleanup allow seamless recovery from interrupted generation jobs without manual intervention or data duplication.
- **Dynamic Resource Auto-Tuning:** Automated memory budget calculation and preventative worker restarts ensure stable execution across varying hardware, from developer laptops to high-end servers.
- **Fast Validation:** A "Shadow Render" capability for rapid prototyping and validation of scene recipes without the overhead of full 3D rendering.
