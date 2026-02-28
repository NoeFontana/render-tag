# v0.1.1 (2026-02-28)

- Phase 2: CI/CD Pipeline Modernization (GitHub Actions) Verification
  Automated Test Command: uv run pytest (Passed)
  Manual Verification Steps:
  1. Review the updated GitHub Action workflow: .github/workflows/release.yml
  2. Confirm that you see:
     - The workflow is triggered by push: tags: - 'v*'
     - There's a build-python job that sets up uv and builds the assets.
     - The build-docker job extracts tags using docker/metadata-action and pushes to ghcr.io.
     - The publish-release job extracts git notes and creates a release using softprops/action-gh-release@v2.
  User Confirmation: Yes (followed best modern practices including provenance attestation)

- Task: Modernize GitHub Action workflow for release
  - Added OIDC permissions for GitHub Actions (attestations and id-token)
  - Added 'actions/attest-build-provenance' to the docker build job to attach provenance metadata to the published image
  - Enabled automatic generation of release notes from softprops/action-gh-release@v2.

- Task: Modify the Docker build job to extract the version string from the tag and apply both semantic and latest tags before pushing to GHCR. Add a publish-release job dependent on artifact builds.
  - Updated docker build job to push to GHCR with semver and latest tags using docker/metadata-action.
  - Added publish-release job to extract git notes and create a GitHub Release with python artifacts using softprops/action-gh-release@v2.

- Task: Add a build-python job to the workflow to set up the uv environment and execute Python build (uv build) to compile .whl and .tar.gz artifacts.
  - Added build-python job using setup-uv.
  - Executed uv build to generate dist artifacts.
  - Added step to upload artifacts for subsequent jobs.

- Task: Modify .github/workflows/release.yml's event trigger to listen exclusively for pushed Git tags (e.g., v*).
  - Updated trigger from push/pull_request on main to push on tags matching 'v*'.

- Phase 1: Local Automation (The Release Script) Verification
  Automated Test Command: uv run pytest (Passed)
  Manual Verification Steps:
  1. Execute the release script: ./scripts/release.sh patch
  2. Confirm that you see: pyproject.toml's version is bumped, CHANGELOG.md is updated with the latest git notes, and a new git commit/tag (e.g., v0.1.1) is successfully created.
  User Confirmation: Yes

- Task: Create scripts/release.sh to encapsulate versioning and tagging logic.
  - Created scripts/release.sh to encapsulate local versioning, tagging, and changelog generation.
  - Implemented hatch version bumping, git notes extraction, and CHANGELOG.md updating.

- Phase 2: Implementation of Static Quality Gates
  Automated tests: uv run pytest tests/unit/test_ci_file.py
  Manual verification:
  1. Verify CI file contains all 4 static quality gate steps.
  2. Confirm the commands used are correct.
  3. Confirm that the workflow still passes as valid YAML.
  User confirmation: Yes.

- Phase 2: Implementation of Static Quality Gates
  Tasks: Add steps for ruff format, ruff check, lint-arch and ty check.
  Summary: Added four static quality gate steps to CI.
  Files Modified: .github/workflows/ci.yml, tests/unit/test_ci_file.py
  Why: Automates style, architectural and type enforcement on every pull request.

- Phase: CI Pipeline Scaffolding and Environment Setup
  Automated tests: uv run pytest tests/unit/test_ci_file.py
  Manual verification:
  1. Verify concurrency settings with grep.
  2. Confirm permissions and workflow_dispatch.
  3. Confirm workflow validity.
  User confirmation: Yes.

- Tasks: Create .github/workflows/ci.yml and Integrate setup-uv.
  Summary: Scaffolded the initial GitHub Actions workflow with uv/setup-uv for fast dependency resolution.
  Files Created: .github/workflows/ci.yml, tests/unit/test_ci_file.py
  Why: Establishes the automated CI pipeline required for quality gates.

- Phase 3 Verified and Complete. The dry-run validation succeeded and tests passed.

- Automated tests executed: CI=true uv run pytest tests/unit/heavy_logic/cli/test_hub_cli.py
  Manual Verification Steps: uv run render-tag push-dataset output/benchmarks/single_tag_locus_v1_std41h12 my_org/my_repo --dry-run
  User confirmed expectations met.

- Automated tests executed: CI=true uv run pytest tests/unit/heavy_logic/cli/test_hub_cli.py
  Manual Verification Steps: uv run pytest test_hub_cli.py
  User confirmed expectations met.

- Task: Debugging and Root Cause Analysis. Wrote a failing test to simulate benchmark directory structure. Bug identified: render_generator assumes _meta.json contains detections, but benchmarks output a rich_truth.json file instead.

- Phase 2 Verification Report
  Automated Tests: uv run pytest tests/unit/generation/test_texture_factory.py
  Manual Verification Steps:
  1. Run scripts/debug_texture.py to generate sample AprilGrid and ChArUco textures.
  2. Inspect output/test_debug/debug_aprilgrid.png and debug_charuco.png.
  3. Verified AprilGrid has tags in every cell + corner squares.
  4. Verified ChArUco has checkerboard + tags in white squares (0,0 is white).
  User Confirmation: Received 'yes' on Feb 17, 2026.

- Task: Implement TextureFactory in src/render_tag/generation/texture_factory.py using OpenCV.
  Summary: Created a high-resolution texture synthesizer for AprilGrid and ChArUco boards. Includes sub-pixel accurate drawing, deterministic hashing, and filesystem caching.
  Files:
  - src/render_tag/generation/texture_factory.py
  - tests/unit/generation/test_texture_factory.py
  Why: Enables generating Mathematically perfect calibration targets as a single texture on a rigid plane, eliminating multi-object artifacts.

- Phase 1 Verification Report
  Automated Tests: uv run pytest tests/unit/core/schema/test_board.py
  Manual Verification Steps:
  1. Open Python REPL: uv run python
  2. Execute validation logic for BoardConfig (AprilGrid/ChArUco constraints).
  3. Verified that valid configs pass and invalid configs (missing fields, geometric violations) raise ValidationError.
  User Confirmation: Received 'yes' on Feb 17, 2026.

- Task: Implement Pydantic validators to enforce marker_size < square_size for ChArUco.
  Summary: Added model_validator to BoardConfig to enforce type-specific requirements (square_size for ChArUco, spacing_ratio for AprilGrid) and geometric constraints.
  Files:
  - src/render_tag/core/schema/board.py
  - tests/unit/core/schema/test_board.py
  Why: Ensures that the board configuration is physically valid before generation begins.

- Task: Create src/render_tag/core/schema/board.py with BoardType and BoardConfig.
  Summary: Implemented Pydantic V2 schemas for AprilGrid and ChArUco calibration boards.
  Files:
  - src/render_tag/core/schema/board.py
  - tests/unit/core/schema/test_board.py
  Why: Provides the configuration contract required for the bit-perfect texture synthesizer and scene integration.

- Phase 2: Backend Engine Integration Verification Report
  Automated Tests: uv run pytest tests/unit/backend/test_engine.py (PASSED)
  Manual Verification: Verified that RenderFacade applies light path settings to BlenderProc mocks.
  User Confirmation: yes

- Task: Backend Engine Integration for Light Paths
  Summary: Updated RenderFacade to apply diffuse, glossy, transmission, and transparency bounces, as well as caustics settings to BlenderProc renderer.
  Files: src/render_tag/backend/engine.py, src/render_tag/backend/mocks/blenderproc_api.py, tests/unit/backend/test_engine.py

- Phase 1: Schema and Core Configuration Verification Report
  Automated Tests: uv run pytest tests/unit/core/schema/test_renderer.py (PASSED)
  Manual Verification: Verified that RendererConfig correctly parses light path overrides from YAML.
  User Confirmation: yes

- Task: Update RendererConfig schema
  Summary: Added total_bounces, diffuse_bounces, glossy_bounces, transmission_bounces, transparent_bounces, and enable_caustics to RendererConfig with CV-optimized defaults.
  Files: src/render_tag/core/schema/renderer.py, tests/unit/core/schema/test_renderer.py

- Verification Report - Phase 2: Backend Engine Integration
  Automated Tests: uv run pytest tests/unit/backend/test_engine_cv_safe.py (PASSED)
  Manual Verification: Verified RenderFacade applies 0.07 threshold and enables guidance passes via mock script.
  User Confirmation: yes

- Task: Update backend engine integration
  Summary: Updated RenderFacade and execute_recipe to apply noise_threshold, max_samples, and OIDN with Albedo/Normal guidance. Enhanced BlenderProc mock to support these methods.
  Files: src/render_tag/backend/engine.py, src/render_tag/backend/mocks/blenderproc_api.py, tests/unit/backend/test_engine_cv_safe.py

- Verification Report - Phase 1: Schema and Core Configuration
  Automated Tests: uv run pytest tests/unit/core/schema/test_renderer.py (PASSED)
  Manual Verification: Validated Noise Threshold: 0.01 via GenConfig test.
  User Confirmation: yes

- Task: Update RendererConfig schema
  Summary: Added noise_threshold, max_samples, enable_denoising, and denoiser_type to RendererConfig. Moved RendererConfig to its own file src/render_tag/core/schema/renderer.py.
  Files: src/render_tag/core/schema/recipe.py, src/render_tag/core/schema/renderer.py, src/render_tag/core/schema/__init__.py, tests/unit/core/schema/test_renderer.py

- Task: Phase 4: Resilient Recovery
  Summary: Implemented the Orchestrator-side logic to handle maintenance restarts when workers exceed memory limits.
  - Updated UnifiedWorkerOrchestrator.release_worker to detect RESOURCE_LIMIT_EXCEEDED status and trigger preventative restarts.
  - Modified execute_recipe to catch RESOURCE_LIMIT_EXCEEDED failure messages and retry immediately without incrementing the standard failure counter.
  - Enhanced backend _on_render to perform post-render memory checks and report exceeded limits to the host.
  - Added unit tests to verify that the orchestrator correctly retries recipes on resource limit exceedance without counting them as failures.
  Files:
  - src/render_tag/orchestration/orchestrator.py
  - src/render_tag/backend/worker_server.py
  - tests/unit/orchestration/test_resilient_recovery.py
  Why: Ensures high availability and stability of long-running generation jobs by treating memory-driven restarts as routine maintenance rather than system failures.

- Task: Phase 3: Worker Sentinel (Enforcement)
  Summary: Implemented real-time memory monitoring and budget enforcement in the worker backend.
  - Added RESOURCE_LIMIT_EXCEEDED status to WorkerStatus schema.
  - Enhanced Telemetry schema to include ram_used_mb.
  - Implemented _check_memory in ZmqBackendServer with explicit garbage collection.
  - Integrated memory checks into both the management heartbeat thread and the main task loop.
  - Updated zmq_server.py to parse --memory-limit-mb and pass it to the server.
  - Added unit tests with mock psutil processes to verify enforcement logic.
  Files:
  - src/render_tag/core/schema/hot_loop.py
  - src/render_tag/backend/worker_server.py
  - src/render_tag/backend/zmq_server.py
  - tests/unit/backend/test_worker_memory.py
  Why: Provides the mechanism to detect and gracefully handle memory growth or leaks in Blender processes, enabling preventative restarts before system instability occurs.

- Task: Phase 2: Dynamic Allocation (Orchestrator)
  Summary: Implemented memory budget calculation and injection logic.
  - Created calculate_worker_memory_budget in src/render_tag/core/resources.py with auto-tuning (75% system RAM) and sane floors.
  - Updated PersistentWorkerProcess to accept memory_limit_mb and pass it via --memory-limit-mb CLI flag.
  - Updated UnifiedWorkerOrchestrator to calculate budget on startup and pass it to workers.
  - Added unit tests for calculation logic and subprocess injection.
  Files:
  - src/render_tag/core/resources.py
  - src/render_tag/orchestration/orchestrator.py
  - src/render_tag/orchestration/worker.py
  - tests/unit/orchestration/test_resource_calc.py
  - tests/unit/orchestration/test_memory_injection.py
  Why: Ensures that generation jobs automatically adapt to the available system RAM, preventing crashes or swapping on lower-spec hardware.

- Task: Update JobInfrastructure for memory limits
  Summary: Added max_memory_mb field to JobInfrastructure in src/render_tag/core/schema/job.py. This field allows specifying a hard memory limit per worker in MB, or leaving it as None for auto-tuning.
  Files:
  - src/render_tag/core/schema/job.py
  - tests/unit/core/test_schema_memory.py
  Why: Foundational schema update for the RAM Telemetry & Auto-Tuning feature, enabling the Orchestrator to communicate memory budgets to workers.

- Phase 2: CLI Integration & Resumption Flow Verification Report
  
  Automated Test Command: uv run pytest tests/integration/test_resumption_cli.py
  Manual Verification Steps:
  1. Generate initial dataset.
  2. Manually corrupt ground_truth.csv.
  3. Run resumption with --resume-from and verify cleanup of corrupted shard and skip of valid shard.
  
  User Confirmation: Yes

- Task: Update CLI generate Command for Resumption
  Summary: Integrated --resume-from flag into the generation pipeline.
  - Modified ConfigLoadingStage to load JobSpec from disk.
  - Updated PreparationStage to use ShardValidator for skipping completed shards.
  - Added skip_execution flag to GenerationContext to bypass ExecutionStage when shard is already complete.
  - Verified with integration tests covering invalid paths, valid skips, and aggressive cleanup of incomplete shards.
  Files:
  - src/render_tag/cli/generate.py
  - src/render_tag/cli/pipeline.py
  - src/render_tag/cli/stages/config_stage.py
  - src/render_tag/cli/stages/prep_stage.py
  - src/render_tag/cli/stages/execution_stage.py
  - src/render_tag/orchestration/validator.py
  - tests/integration/test_resumption_cli.py
  Why: Provides a robust and user-friendly way to resume interrupted or crashed generation jobs without manual cleanup.

- Phase 1: Deterministic Sharding & Validation Logic Verification Report
  
  Automated Test Command: uv run pytest tests/unit/core/test_job_spec_determinism.py tests/unit/orchestration/test_validator.py
  Manual Verification Steps:
  1. Verify JobSpec shard index calculation in Python REPL.
  2. Verify ShardValidator aggressive cleanup by creating invalid files and checking their deletion.
  
  User Confirmation: Yes

- Task: Implement ShardValidator
  Summary: Created ShardValidator class in src/render_tag/orchestration/validator.py. Implemented logic to check CSV row counts and JSON existence/validity. Added aggressive cleanup for invalid shards.
  Files:
  - src/render_tag/orchestration/validator.py
  - tests/unit/orchestration/test_validator.py
  Why: Necessary for identifying missing or incomplete dataset parts before resuming jobs.

- Task: Update JobSpec for Deterministic Mapping
  Summary: Implemented get_total_shards and get_scene_indices in JobSpec to ensure consistent scene assignments across shards.
  Files:
  - src/render_tag/core/schema/job.py
  - tests/unit/core/test_job_spec_determinism.py
  Why: Necessary for 'Smart Resume' logic to know exactly which scenes belong to which shard file on disk.

- Phase: Refactoring & Verification
  Summary: Refactored all sampling functions in src/render_tag/generation/ to use numpy.random.Generator. Isolated core constants. Verified determinism with new integration test.
  Files: src/render_tag/generation/compiler.py, src/render_tag/generation/layouts.py, src/render_tag/generation/scene.py, src/render_tag/core/constants.py, src/render_tag/core/__init__.py, tests/unit/core/test_generator_reproducibility.py
  Why: Ensures that scene generation is 100% deterministic and reproducible, decoupled from global random state.

- Phase: Infrastructure & Enforcement
  Summary: Updated .importlinter to block 'random' in render_tag.generation. Initialized numpy RNG in Generator class.
  Files: .importlinter, src/render_tag/generation/scene.py, tests/unit/core/test_determinism_imports.py, tests/unit/core/test_generator_rng.py
  Why: Establish a foundation for deterministic scene generation by enforcing the use of explicitly passed RNGs instead of global random state.

- Phase Completion Report: Phase 3
  Automated Test Command: uv run pytest tests/unit/core/test_migration_disk.py tests/unit/core/test_migration_yaml.py tests/unit/core/test_migration_jobspec.py tests/unit/core/test_migrator.py
  Manual Verification:
  1. Verified legacy configuration files are automatically upgraded on disk.
  2. Verified legacy job spec files are automatically upgraded on disk.
  User Confirmation: yes

- Task: Final Integration Test
  Summary: Verified that legacy configuration files are automatically upgraded on disk to version 1.0 when running the generation pipeline. Fixed JobSpec initialization in ConfigResolver.
  Files: src/render_tag/core/config_loader.py, src/render_tag/core/config.py, src/render_tag/core/schema/job.py, src/render_tag/backend/zmq_server.py
  Why: To ensure end-to-end functionality of the strict schema versioning and automatic upgrade system.

- Task: Implement On-Disk Upgrade Logic
  Summary: Added upgrade_file_on_disk to SchemaMigrator. Integrated it into load_config and JobSpec.from_file. Updated ZMQ server to use from_file.
  Files: src/render_tag/core/migration.py, src/render_tag/core/config.py, src/render_tag/core/schema/job.py, src/render_tag/backend/zmq_server.py, tests/unit/core/test_migration_disk.py
  Why: To provide a self-healing configuration library where legacy files are automatically upgraded to the current version upon access.

- Phase Completion Report: Phase 2
  Automated Test Command: uv run pytest tests/unit/core/test_migration_yaml.py tests/unit/core/test_migration_jobspec.py tests/unit/core/test_migrator.py
  Manual Verification:
  1. Verified legacy.yaml migrated to version '1.0'.
  2. Verified legacy_job.json migrated to version '1.0'.
  User Confirmation: yes

- Task: Implement TDD for JobSpec Migration
  Summary: Integrated SchemaMigrator into JobSpec.from_json. Updated backend worker to use this method for loading manifests. Made JobSpec.version required.
  Files: src/render_tag/core/schema/job.py, src/render_tag/backend/zmq_server.py, tests/unit/core/test_migration_jobspec.py
  Why: To ensure that existing job manifests can be loaded and automatically upgraded to the current schema version.

- Task: Implement TDD for YAML Migration
  Summary: Integrated SchemaMigrator into load_config utility. Made GenConfig.version required to ensure migration is performed.
  Files: src/render_tag/core/config.py, tests/unit/core/test_migration_yaml.py
  Why: To automate the upgrade of legacy YAML configuration files to version 1.0.

- Phase Completion Report: Phase 1
  Automated Test Command: uv run pytest tests/unit/core/test_migrator.py tests/unit/core/test_config.py tests/unit/core/test_job_spec.py
  Manual Verification:
  1. Verified GenConfig version default is '1.0'.
  2. Verified JobSpec version default is '1.0'.
  User Confirmation: yes

- Task: Update JobSpec Schema
  Summary: Added mandatory version field to the JobSpec Pydantic model to ensure long-term data auditability.
  Files: src/render_tag/core/schema/job.py
  Why: To support future schema migrations for job manifests.

- Task: Create SchemaMigrator utility
  Summary: Created a centralized migration engine to handle schema upgrades before Pydantic validation. Supports sequential transformations.
  Files: src/render_tag/core/migration.py, tests/unit/core/test_migrator.py
  Why: To allow safe refactoring of schemas without breaking historical data access.

- Verification Report for Phase 5: Verification and Benchmarking
  - Automated tests: All integration tests passing
  - Manual verification: Executed PPM sweep and audit; confirmed PPM metadata in output formats
  - User confirmation: Received

- Verification Report for Phase 4: Data Export and Auditing
  - Automated tests: N/A
  - Manual verification: Validated tags.csv, rich_truth.json, and audit CLI output with mock generation
  - User confirmation: Received

- Verification Report for Phase 3: Generator Logic Integration
  - Automated tests: uv run pytest tests/integration/test_ppm_sampling.py (PASSED)
  - Manual verification: Executed integration test suite manually
  - User confirmation: Received

- Verification Report for Phase 2: Math Kernel Implementation
  - Automated tests: uv run pytest tests/unit/test_ppm_math.py (PASSED)
  - Manual verification: Executed test suite manually
  - User confirmation: Received

- Verification Report for Phase 1: Schema and Contract Update
  - Automated tests: N/A (Schema only)
  - Manual verification: Validated with configs/test_ppm.yaml
  - User confirmation: Received

- Phase 3 Verification Report
  Automated Test Command: uv run pytest tests/unit/backend/test_bootstrap.py tests/unit/orchestration/test_environment_injection.py
  Manual Verification Steps:
  1. Verify End-to-End Generation: RENDER_TAG_FORCE_MOCK=1 uv run render-tag generate --config configs/test_minimal.yaml --output output/verify_final --scenes 1
  2. Confirm Output: ls output/verify_final/images output/verify_final/tags_shard_0.csv
  3. Inspect Logs: Check for 'Worker worker-0 is ready.' and 'Dataset generated successfully!'
  User Confirmation: yes

- Task: Refactor backend scripts to use bootstrap.py and remove legacy sys.path manipulation.
  Summary: Refactored zmq_server.py, executor.py, bridge.py, and writers.py to use the new bootstrap module. Removed redundant and brittle sys.path hacks. Verified the full generation pipeline with RENDER_TAG_FORCE_MOCK=1.
  Files: src/render_tag/backend/zmq_server.py, src/render_tag/backend/executor.py, src/render_tag/backend/bridge.py, src/render_tag/data_io/writers.py
  Why: To centralize environment synchronization and eliminate brittle path manipulation across the backend codebase.

- Task: Orchestration Handshake for Blender environment synchronization.
  Summary: Created environment utility to detect venv site-packages. Updated PersistentWorkerProcess and DockerExecutor to inject RENDER_TAG_VENV_SITE_PACKAGES and set PYTHONNOUSERSITE=1.
  Files: src/render_tag/common/environment.py, src/render_tag/orchestration/persistent_worker.py, src/render_tag/orchestration/executors.py, tests/unit/orchestration/test_environment_injection.py
  Why: To ensure Blender has access to the correct dependencies and is isolated from system packages during orchestration.

- Phase 1 Verification Report
  Automated Test Command: uv run pytest tests/unit/backend/test_bootstrap.py
  Manual Verification Steps:
  1. Verify Environment Discovery: uv run python -c "from render_tag.backend.bootstrap import setup_environment; setup_environment(); import pydantic; print('Bootstrap Success')"
  2. Confirm Output: Bootstrap Success
  User Confirmation: yes

- Task: Create src/render_tag/backend/bootstrap.py with environment discovery logic.
  Summary: Implemented bootstrap.py to synchronize Blender's Python environment with the project's venv. It supports orchestration mode (via env var) and dev mode (via .venv discovery). Includes fail-fast logic for pydantic.
  Files: src/render_tag/backend/bootstrap.py, tests/unit/backend/test_bootstrap.py
  Why: To eliminate brittle sys.path hacks and ensure dependency parity between Host and Backend.

- Phase 3: Workflow Integration & Finalization
  Automated Tests: uv run ruff check . && uv run render-tag lint-arch
  Manual Verification: Verified that the architectural linter is integrated into the official linting workflow and the codebase is clean.
  User Confirmation: yes

- Phase 2: CLI Integration
  Automated Tests: uv run pytest tests/integration/test_cli_arch.py
  Manual Verification: Verified the lint-arch CLI command exists, runs correctly, and detects violations as expected.
  User Confirmation: yes

- Phase 1: Environment & Tooling Setup
  Automated Tests: uv run lint-imports
  Manual Verification: Verified that import-linter is installed, configured, and correctly validates the codebase.
  User Confirmation: yes

- Task: Implement High-Precision Annotations & Metadata
  Summary: Implemented COCO keypoint formatting in annotations.py. Created dataset_info.py to generate dataset_info.json with SHA256 integrity hash, provenance (git, env), and metadata. Integrated this into the experiment CLI runner.
  Files: src/render_tag/data_io/annotations.py, src/render_tag/audit/dataset_info.py, src/render_tag/cli/experiment.py
  Why: To provide self-describing, integrity-verified datasets for calibration benchmarking.

- Task: Implement Experiment Infrastructure for Calibration Suite
  Summary: Created calibration configs (checkerboard, aprilgrid) and master campaign config. Implemented 'Campaign' orchestration logic to support hierarchical experiment execution and metadata injection (intent). Added 'intent' field to DatasetConfig.
  Files: configs/..., src/render_tag/orchestration/experiment*, src/render_tag/core/config.py
  Why: To support the Locus Bench calibration phase requirements.

- Task: Clean up Git repository
  Summary: Removed all binary assets from the git repository and updated .gitignore to exclude binary file formats in the assets directory.
  Files: .gitignore, and many files in assets/
  Why: Reduces repository size and enforces the new pattern of storing large assets on Hugging Face.

- Task: Integrate AssetProvider into Generator
  Summary: Modified Generator in src/render_tag/generation/scene.py to use AssetProvider for resolving HDRI, background texture, and tag texture paths. This enables automatic downloading of missing assets from Hugging Face during scene generation.
  Files: src/render_tag/generation/scene.py, tests/unit/test_generator_assets.py
  Why: Completes the integration of on-demand asset retrieval into the core generation pipeline.

- Task: Implement assets sync CLI command
  Summary: Renamed the existing 'pull' command to 'sync' and added 'pull' as a hidden alias for backward compatibility. Updated output messages to use 'Synchronizing'.
  Files: src/render_tag/cli/assets.py, tests/unit/test_cli_assets.py
  Why: Aligns the CLI with the implementation plan and user expectations for asset management.

- Task: Create AssetProvider abstraction
  Summary: Implemented AssetProvider in src/render_tag/data_io/assets.py to handle resolving asset paths with on-demand downloading from Hugging Face using hf_hub_download.
  Files: src/render_tag/data_io/assets.py, tests/unit/test_asset_provider.py
  Why: Provides a seamless way for the generator and other components to fetch missing assets during execution.

- Task: Add huggingface_hub dependency and update environment
  Summary: Moved huggingface-hub from optional-dependencies to core dependencies in pyproject.toml and verified installation.
  Files: pyproject.toml, uv.lock
  Why: Required for on-demand asset downloading in the Generator and for the new sync CLI command.

- Phase 4: Provenance & Verification Verification Report
  Automated tests: uv run pytest tests/unit/test_manifest.py tests/unit/test_cli_manifest_integration.py tests/unit/test_cli_verify.py
  Manual Verification: Successfully generated dataset with manifest.json and verified integrity/tampering via 'render-tag job verify'.
  User Confirmation: Yes

- Phase 3: Job-Driven Execution Engine Verification Report
  Automated tests: uv run pytest tests/unit/test_cli_job_execution.py
  Manual Verification: Verified --job integration, environment guard (tamper check), and CLI flag overrides with warnings.
  User Confirmation: Yes

- Phase 2: CLI Command - lock Verification Report
  Automated tests: uv run pytest tests/unit/test_cli_job.py
  Manual Verification: Successfully ran 'render-tag lock' and verified generated JSON content.
  User Confirmation: Yes

- Phase 1: Core Schema & Identity Verification Report
  Automated tests: uv run pytest tests/unit/test_asset_manager.py tests/unit/test_job_spec.py tests/unit/test_fingerprinting.py
  Manual Verification: Verified JobSpec immutability, env fingerprinting, and asset hashing in Python shell.
  User Confirmation: Yes

- Phase: Final Cleanup & Validation
  Automated Tests: pytest tests/integration/test_hot_loop_render.py tests/integration/test_persistent_sharding.py tests/unit/test_unified_orchestrator.py (All Passed)
  Manual Verification: Verified speedup and architectural simplification via updated benchmark script.
  User Confirmation: Explicitly confirmed by user.

- Task: Comprehensive Integration Benchmark
  Summary: Updated the benchmark suite to utilize the UnifiedWorkerOrchestrator. Confirmed that the architectural simplification did not regress performance; the hot-loop still provides ~80x speedup over the ephemeral (one-shot) path in mock environments.
  Files:
  - render-tag/scripts/benchmark_hot_loop.py

- Task: Codebase-wide Retirement of Boilerplate
  Summary: Finalized the architectural cleanup by reducing 'executor.py' to a lightweight 50-line wrapper around the core rendering loop. Updated 'DockerExecutor' to maintain compatibility while benefiting from the simplified backend structure. Verified that all 'setup_mocks' and 'try/except' boilerplate has been eliminated from core modules.
  Files:
  - render-tag/src/render_tag/backend/executor.py
  - render-tag/src/render_tag/orchestration/executors.py

- Phase: Geometry & Renderer Facade
  Automated Tests: pytest tests/integration/test_hot_loop_render.py tests/integration/test_persistent_sharding.py (All Passed)
  Manual Verification: Verified that refactored render loop successfully employs the Renderer facade and pure-math geometry layer.
  User Confirmation: Explicitly confirmed by user.

- Task: Renderer Facade Implementation
  Summary: Implemented the 'RenderFacade' class to provide a high-level API for scene construction and rendering. Refactored 'render_loop.py' to use this facade, effectively decoupling the core image generation flow from the underlying BlenderProc and Blender internals. This simplifies maintenance and enables easier swapping of the rendering backend in the future.
  Files:
  - render-tag/src/render_tag/backend/renderer.py
  - render-tag/src/render_tag/backend/render_loop.py

- Task: Pure-Python Geometry Layer
  Summary: Migrated coordinate transformations, normal calculation, and angle of incidence math from the Blender backend to a pure-Python library ('projection_math.py'). Refactored 'projection.py' to use these environment-agnostic functions, facilitating easier testing and better logic isolation.
  Files:
  - render-tag/src/render_tag/geometry/projection_math.py
  - render-tag/src/render_tag/backend/projection.py

- Task: Create UnifiedWorkerOrchestrator
  Summary: Consolidated the divergence between ephemeral (Cold) and persistent (Hot) execution paths into a single UnifiedWorkerOrchestrator. All Blender execution now flows through the ZMQ-based worker pattern, ensuring consistent telemetry, logging, and error handling. Legacy LocalExecutor has been retired in favor of this unified model.
  Files:
  - render-tag/src/render_tag/orchestration/unified_orchestrator.py
  - render-tag/src/render_tag/orchestration/executors.py
  - render-tag/src/render_tag/orchestration/persistent_worker.py
  - render-tag/src/render_tag/backend/zmq_server.py

- Task: Refactor zmq_server.py for Dual-Mode Execution
  Summary: Updated the ZmqBackendServer to support an ephemeral mode via 'max_renders'. In this mode, the server automatically shuts down after processing a set number of RENDER commands, enabling unification of the one-off and persistent execution paths.
  Files:
  - render-tag/src/render_tag/backend/zmq_server.py
  - render-tag/tests/integration/test_ephemeral_worker.py

- Phase: Centralized Blender Bridge
  Automated Tests: pytest tests/unit/test_blender_bridge.py tests/integration/test_hot_loop_render.py tests/integration/test_persistent_sharding.py (All Passed)
  Manual Verification: Verified that backend refactor successfully employs BlenderBridge for dependency management and auto-mocking.
  User Confirmation: Explicitly confirmed by user.

- Task: Refactor Backend Modules to use Bridge
  Summary: Refactored all backend modules (scene, assets, camera, projection, layouts, render_loop, zmq_server) to use the centralized BlenderBridge. Removed approximately 140 lines of repetitive try/except blocks and manual mock setup code. Standardized NumPy access across the backend.
  Files:
  - render-tag/src/render_tag/backend/assets.py
  - render-tag/src/render_tag/backend/camera.py
  - render-tag/src/render_tag/backend/layouts.py
  - render-tag/src/render_tag/backend/projection.py
  - render-tag/src/render_tag/backend/scene.py
  - render-tag/src/render_tag/backend/render_loop.py
  - render-tag/src/render_tag/backend/zmq_server.py
  - render-tag/src/render_tag/backend/bridge.py

- Task: Create src/render_tag/backend/bridge.py (The Provider)
  Summary: Implemented a centralized service locator for Blender, BlenderProc, and NumPy. Features automated environment detection and mock serving, eliminating the need for repetitive try/except blocks and manual mock injection in backend modules.
  Files:
  - render-tag/src/render_tag/backend/bridge.py
  - render-tag/tests/unit/test_blender_bridge.py

- Phase: Observability & Optimization
  Automated Tests: pytest tests/unit/test_vram_guardrails.py tests/unit/test_telemetry_auditor.py (All Passed)
  Manual Verification: Executed benchmark and telemetry scripts, verified VRAM protection logic and Polars-based analysis.
  User Confirmation: Explicitly confirmed by user.

- Task: Final Performance Benchmarking
  Summary: Implemented benchmarking scripts to quantify the throughput improvements of the Hot Loop architecture. In mock environments, the speedup exceeds 100x by eliminating per-image process initialization overhead.
  Files:
  - render-tag/scripts/benchmark_hot_loop.py

- Task: Structured Logging & Telemetry Dashboard
  Summary: Implemented TelemetryAuditor which uses Polars to ingest worker telemetry. This enables vectorized analysis of throughput, VRAM consumption, and worker health over time.
  Files:
  - render-tag/src/render_tag/tools/telemetry_auditor.py
  - render-tag/tests/unit/test_telemetry_auditor.py

- Task: Implement VRAM Guardrails
  Summary: Added automatic memory protection to the WorkerPool. Workers are now monitored for VRAM usage upon release; if they exceed a configurable threshold, they are automatically restarted to prevent OOM errors and clear memory fragmentation.
  Files:
  - render-tag/src/render_tag/orchestration/worker_pool.py
  - render-tag/tests/unit/test_vram_guardrails.py

- Phase: Hot Loop Rendering & State Management
  Automated Tests: pytest tests/integration/test_backend_warmup.py tests/integration/test_hot_loop_render.py tests/integration/test_persistent_sharding.py (All Passed)
  Manual Verification: Executed Hot Loop Performance Benchmark, verified single-initialization multi-render flow and high throughput in persistent state.
  User Confirmation: Explicitly confirmed by user.

- Task: Hot Loop Integration Test
  Summary: Verified full Hot Loop pipeline by generating 10 images through a persistent worker managed by a WorkerPool. Ensured that initialization overhead is only incurred once and subsequent renders are high-throughput. Improved backend modularity by implementing 'setup_mocks' across all core modules.
  Files:
  - render-tag/src/render_tag/backend/zmq_server.py
  - render-tag/src/render_tag/backend/render_loop.py
  - render-tag/src/render_tag/orchestration/worker_pool.py
  - render-tag/tests/integration/test_persistent_sharding.py

- Task: Implement Partial Reset in blender_main.py
  Summary: Extracted core rendering logic into a reusable 'render_loop.py'. Implemented 'RENDER' and 'RESET' commands in the ZmqBackendServer. 'RESET' clears the object pool without reloading heavy environment assets. Updated mock Blender API to support complex rendering calls during testing.
  Files:
  - render-tag/src/render_tag/backend/render_loop.py
  - render-tag/src/render_tag/backend/executor.py
  - render-tag/src/render_tag/backend/zmq_server.py
  - render-tag/tests/integration/test_hot_loop_render.py
  - render-tag/tests/mocks/blender_api.py
  - render-tag/tests/mocks/blenderproc_api.py

- Task: Implement Backend Warm-up Logic
  Summary: Added 'load_assets' command to pre-load HDRIs and other heavy assets into VRAM. Integrated GPUtil for real-time VRAM monitoring. Improved mock Blender API for better testability of persistent backend features.
  Files:
  - render-tag/src/render_tag/backend/zmq_server.py
  - render-tag/tests/integration/test_backend_warmup.py
  - render-tag/tests/mocks/blender_api.py
  - render-tag/tests/mocks/blenderproc_api.py

- Phase: Persistent Worker Lifecycle
  Automated Tests: pytest tests/unit/test_persistent_worker.py tests/unit/test_worker_pool.py (All Passed)
  Manual Verification: Executed WorkerPool demonstration script, verified multi-worker startup and automatic resilience/restart logic.
  User Confirmation: Explicitly confirmed by user.

- Task: Implement WorkerPool Orchestrator
  Summary: Implemented a managed pool of persistent Blender workers. Features include broadcast commands, automated health-triggered restarts, and thread-safe worker acquisition via a queue.
  Files:
  - render-tag/src/render_tag/orchestration/worker_pool.py
  - render-tag/tests/unit/test_worker_pool.py

- Task: Implement PersistentWorkerProcess Manager
  Summary: Implemented the lifecycle manager for persistent Blender subprocesses. Features include ZMQ-based health monitoring, startup synchronization, and graceful shutdown. Optimized for fast failure detection and reliable communication.
  Files:
  - render-tag/src/render_tag/orchestration/persistent_worker.py
  - render-tag/tests/unit/test_persistent_worker.py

- Phase: Communication & Protocol Foundation
  Automated Tests: pytest tests/unit/test_hot_loop_schema.py tests/unit/test_zmq_client.py tests/integration/test_zmq_loopback.py (All Passed)
  Manual Verification: Verified Host-Backend loopback via ZMQ connectivity script.
  User Confirmation: Explicitly confirmed by user.

- Task: Implement ZMQ Backend Server (Skeleton)
  Summary: Implemented the initial ZmqBackendServer that listens for commands and provides status/telemetry. Verified Host-to-Backend loopback connectivity via integration tests.
  Files:
  - render-tag/src/render_tag/backend/zmq_server.py
  - render-tag/tests/integration/test_zmq_loopback.py

- Task: Implement ZMQ Host Client
  Summary: Implemented a ZmqHostClient using the REQ pattern to send JSON-serialized commands to the persistent backend. Added support for timeouts and error handling.
  Files:
  - render-tag/src/render_tag/orchestration/zmq_client.py
  - render-tag/tests/unit/test_zmq_client.py

- Task: Define ZMQ Message Schemas (Pydantic)
  Summary: Defined Pydantic models for Host-Backend communication (Command, Response, Telemetry) and implemented deterministic state hashing for scene reproducibility.
  Files:
  - render-tag/src/render_tag/schema/hot_loop.py
  - render-tag/tests/unit/test_hot_loop_schema.py

- Phase Verification Report: Phase 5 - Comparative Analysis (Drift Detection)
  Automated Tests: cd render-tag && uv run pytest tests/unit/test_auditor_diff.py tests/unit/test_cli_audit.py (All PASSED)
  Manual Verification:
  1. Create two dummy datasets with different tag counts.
  2. Run 'render-tag audit diff output/d1 output/d2'.
  3. Confirm statistical drift table shows correct deltas (e.g. +1 tag, +1 image).
  User Confirmation: Received 'yes' on 2026-02-05.

- Task: Audit Diff Command
  Summary: Implemented AuditDiff to calculate deltas between audit reports. Refactored 'audit' CLI into sub-commands: 'run' and 'diff'. 'diff' allows comparing two datasets to detect statistical drift in tag count, distance, angle, and quality score.
  Files:
  - render_tag/src/render_tag/data_io/auditor.py
  - render_tag/src/render_tag/cli.py
  - render_tag/tests/unit/test_auditor_diff.py
  - render_tag/tests/unit/test_cli_audit.py

- Phase Verification Report: Phase 4 - Reporting & Visualization
  Automated Tests: cd render-tag && uv run pytest tests/unit/test_auditor_reporting.py tests/unit/test_auditor_viz.py (All PASSED)
  Manual Verification:
  1. Run auditor on test dataset.
  2. Verify 'audit_report.json' is created with correct schema.
  3. Verify 'audit_dashboard.html' is generated and displays interactive Plotly charts.
  User Confirmation: Received 'yes' on 2026-02-05.

- Task: Reporting & Visualization
  Summary: Implemented AuditResult JSON serialization using Pydantic. Added DashboardGenerator using Plotly to create standalone HTML dashboards with histograms for distance, angle, and lighting. Integrated both into the 'audit' command.
  Files:
  - render_tag/src/render_tag/data_io/auditor_viz.py
  - render_tag/src/render_tag/cli.py
  - render_tag/tests/unit/test_auditor_reporting.py
  - render_tag/tests/unit/test_auditor_viz.py
  - render_tag/pyproject.toml
  - render_tag/uv.lock

- Phase Verification Report: Phase 3 - Quality Gates & Outlier Identification
  Automated Tests: cd render-tag && uv run pytest tests/unit/test_auditor_gates.py tests/unit/test_auditor_outliers.py (All PASSED)
  Manual Verification:
  1. Create quality_gate.yaml with a failing threshold (e.g., score > 90).
  2. Run 'render-tag audit output/audit_test --gate quality_gate.yaml'.
  3. Confirm command exits with code 1 and displays failures.
  4. Verify 'outliers/' directory is managed.
  User Confirmation: Received 'yes' on 2026-02-05.

- Task: Quality Gate Logic & Outlier Management System
  Summary: Implemented GateEnforcer to evaluate datasets against configurable rules in quality_gate.yaml. Added OutlierExporter to identify and symlink problematic frames (e.g. impossible poses) for manual review. Integrated gates into the CLI with hard-failure logic for CI/CD.
  Files:
  - render_tag/src/render_tag/data_io/auditor.py
  - render_tag/src/render_tag/data_io/auditor_schema.py
  - render_tag/src/render_tag/cli.py
  - render_tag/tests/unit/test_auditor_gates.py
  - render_tag/tests/unit/test_auditor_outliers.py

- Phase Verification Report: Phase 2 - Core KPI Engine
  Automated Tests: cd render-tag && uv run pytest tests/unit/test_auditor_geometry.py tests/unit/test_auditor_advanced.py tests/unit/test_dataset_auditor.py (All PASSED)
  Manual Verification:
  1. Run auditor on Phase 1 dataset.
  2. Verify detailed stats for Distance, Angle, and Lighting are displayed (via next CLI update).
  3. Verify heuristic score calculation.
  User Confirmation: Received 'yes' on 2026-02-05.

- Task: Geometric Metric Calculations & Environmental Metrics
  Summary: Implemented GeometryAuditor, EnvironmentalAuditor, and IntegrityAuditor. Added DatasetAuditor to orchestrate the full audit and calculate a heuristic quality score.
  Files:
  - render_tag/src/render_tag/data_io/auditor.py
  - render_tag/tests/unit/test_auditor_geometry.py
  - render_tag/tests/unit/test_auditor_advanced.py
  - render_tag/tests/unit/test_dataset_auditor.py

- Phase Verification Report: Phase 1 - Foundation & Data Ingestion
  Automated Tests: cd render-tag && uv run pytest tests/unit/test_auditor_ingestion.py tests/unit/test_cli_audit.py (All PASSED)
  Manual Verification:
  1. Generate test dataset (2 scenes)
  2. Run 'render-tag audit output/audit_test'
  3. Confirm PASSED status and correct counts.
  User Confirmation: Received 'yes' on 2026-02-05.

- Task: CLI Skeleton for Audit Command
  Summary: Added 'audit' command to Typer CLI in src/render_tag/cli.py. The command currently performs basic dataset loading and displays tag/image counts.
  Files:
  - render_tag/src/render_tag/cli.py
  - render_tag/tests/unit/test_cli_audit.py

- Task: Define Audit Data Models and Polars Ingestion
  Summary: Implemented DatasetReader using Polars for high-performance ingestion of tags.csv and sidecar metadata. Added Pydantic schemas for audit reports.
  Files:
  - render_tag/src/render_tag/data_io/auditor.py
  - render_tag/src/render_tag/data_io/auditor_schema.py
  - render_tag/tests/unit/test_auditor_ingestion.py
  - render_tag/pyproject.toml
  - render_tag/uv.lock

- Task: Phase 4: Integration & Hot Loop Verification
  Summary: Finalized end-to-end persistent execution. Moved BOARD creation out of per-scene setup. Integrated Benchmarker to verify speedup. Verified pixel consistency against baseline.
  Files: src/render_tag/backend/executor.py
  Why: Completes the 'Hot Loop' optimization, providing a stable and high-throughput generation pipeline.

- Task: Phase 3: Resource Pooling (Tags & Materials)
  Summary: Implemented AssetPool in assets.py to reuse Tag planes via visibility toggling. Refactored apply_tag_texture to reuse Blender materials by updating texture nodes in-place. Added periodic orphan purging in executor.py.
  Files: src/render_tag/backend/assets.py, src/render_tag/backend/executor.py, tests/unit/test_backend_pooling.py
  Why: Reusing objects and materials significantly reduces memory churn and data-block overhead, which is critical for maintaining high performance in the 'Hot Loop'.

- Task: Phase 2: Persistent World & Lazy HDRI Loading
  Summary: Refactored setup_background in scene.py to implement lazy loading. It now checks the active Blender World node tree and only reloads the HDRI if the path differs from the requested one. Added unit tests with mocked Blender context.
  Files: src/render_tag/backend/scene.py, tests/unit/test_backend_world.py
  Why: HDRI loading is a major performance bottleneck in the render loop. Lazy loading keeps assets warm in VRAM across scenes.

- Task: Phase 1: Performance Instrumentation & Baseline
  Summary: Created benchmarking.py utility. Integrated Benchmarker into executor.py to track timing of Blender init, setup, rendering, and saving. Established a 10-scene baseline (~4.5s).
  Files: src/render_tag/tools/benchmarking.py, src/render_tag/backend/executor.py
  Why: To provide quantitative data for verifying the speedup from 'Hot Loop' optimizations.

- Task: Phase 2: Blender Backend Implementation
  Summary: Implemented setup_sensor_dynamics in backend/camera.py to map rolling_shutter_duration_ms to Blender's Cycles settings. Added warnings for non-Cycles engines. Updated executor.py to pass dynamics data from recipes.
  Files: src/render_tag/backend/camera.py, src/render_tag/backend/executor.py, tests/unit/test_rolling_shutter_backend.py
  Why: To leverage Blender's native rolling shutter simulation for realistic geometric warping in synthetic data.

- Task: Phase 1: Schema & Configuration Update
  Summary: Refactored CameraConfig and CameraRecipe to group dynamic artifacts under sensor_dynamics. Added rolling_shutter_duration_ms with validation and backward compatibility properties. Updated Generator to populate the new structure.
  Files: src/render_tag/config.py, src/render_tag/schema.py, src/render_tag/generator.py, tests/unit/test_rolling_shutter_schema.py
  Why: To provide a structured and extensible way to simulate complex sensor artifacts like rolling shutter.

- Phase 3 Verification Report
  Automated Tests: tests/unit/test_asset_validator.py, tests/unit/test_asset_manager.py (Passed)
  Manual Verification: Simulated missing assets and verified CLI prompt/failure logic.
  User Confirmation: Explicitly provided by user.
  Status: Phase Complete.

- Task: Phase 3 Runtime Safety & Pre-Flight Checks
  Summary: Implemented AssetValidator to check for hydrated local asset cache. Integrated pre-flight check into generate command with interactive prompt.
  Files: src/render_tag/tools/validator.py, src/render_tag/cli.py, tests/unit/test_asset_validator.py
  Why: To prevent generation failures due to missing binary assets and provide a seamless onboarding experience.

- Phase 2 Verification Report
  Automated Tests: tests/unit/test_cli.py (Passed)
  Manual Verification: Verified assets command group and subcommands help text.
  User Confirmation: Explicitly provided by user.
  Status: Phase Complete.

- Phase 1 Verification Report
  Automated Tests: tests/unit/test_asset_manager.py (Passed)
  Manual Verification: Verified directory structure creation and code review.
  User Confirmation: Explicitly provided by user.
  Status: Phase Complete.

- Task: Implement AssetManager Class
  Summary: Created orchestration/assets.py module with AssetManager class. Integrated huggingface_hub for bidirectional sync and implemented strict directory contract.
  Files: src/render_tag/orchestration/assets.py, tests/unit/test_asset_manager.py
  Why: To centralize binary asset management and enable hermetic reproducibility via remote SSoT.

- Task: Phase 4 Verification & Documentation
  Summary: Ran full test suite to ensure no regressions. Updated README.md with instructions and examples for using local, docker, and mock executors.
  Files: README.md
  Why: To provide clear guidance to users on how to leverage the new pluggable executor system.

- Phase 3 Verification Report
  Automated Tests: tests/unit/test_executors.py, tests/integration/test_executor_mock.py (Passed)
  Manual Verification: Verified mock executor with minimal config.
  User Confirmation: Explicitly provided by user.
  Status: Phase Complete.

- Task: Phase 3 Docker Implementation
  Summary: Implemented DockerExecutor with volume mapping. Added an integration test for the mock executor to verify the pluggable architecture.
  Files: src/render_tag/orchestration/executors.py, tests/integration/test_executor_mock.py, configs/test_minimal.yaml
  Why: To provide containerized rendering support and verify the end-to-end integration.

- Task: Implement DockerExecutor
  Summary: Implemented DockerExecutor class with volume mapping and docker run command construction. Updated ExecutorFactory to support 'docker' type.
  Files: src/render_tag/orchestration/executors.py, tests/unit/test_executors.py
  Why: To enable hermetic, containerized rendering runs.

- Phase 2 Verification Report
  Automated Tests: tests/unit/test_cli.py, tests/unit/test_executors.py (Passed)
  Manual Verification: Verified --help and --executor mock.
  User Confirmation: Explicitly provided by user.
  Status: Phase Complete.

- Task: Phase 2 CLI & Orchestration Update
  Summary: Refactored generate command to use RenderExecutor instead of hardcoded subprocess. Added --executor flag. Updated sharding logic to propagate executor choice.
  Files: src/render_tag/cli.py, src/render_tag/orchestration/sharding.py, tests/unit/test_cli.py
  Why: To enable switching between different rendering environments via the CLI.

- Phase 1 Verification Report
  Automated Tests: cd render-tag && uv run pytest tests/unit/test_executors.py (Passed)
  Manual Verification: Smoke tested ExecutorFactory.
  User Confirmation: Explicitly provided by user.
  Status: Phase Complete.

- Task: Implement LocalExecutor
  Summary: Migrated subprocess.run logic from cli.py to LocalExecutor. Improved error reporting and script path resolution.
  Files: src/render_tag/orchestration/executors.py, tests/unit/test_executors.py
  Why: To encapsulate local execution logic within the new RenderExecutor abstraction.

- Task: Define RenderExecutor Protocol
  Summary: Created executors.py module defining the RenderExecutor protocol, a LocalExecutor stub, a MockExecutor, and an ExecutorFactory.
  Files: src/render_tag/orchestration/executors.py, tests/unit/test_executors.py
  Why: To provide a clean abstraction for different rendering engines (local, containerized, cloud).

- Task: Create tests/unit/test_cli_skip_render.py
  Summary: Added unit tests to verify that the --skip-render flag correctly generates recipes without launching Blender, including support for sharding.
  Files: tests/unit/test_cli_skip_render.py
  Why: To provide fast integration-style tests that verify the recipe generation logic without the slow Blender overhead.

- Phase 2: Enhanced Pre-Flight Validation
  Summary: Expanded RecipeValidator to check for asset existence and integrated it into the 'generate' command to catch errors before launching Blender.
  Files: src/render_tag/tools/validator.py, src/render_tag/cli.py, tests/unit/test_validator_enhanced.py, tests/unit/test_cli_validation.py
  Why: To catch common configuration and geometric errors earlier in the pipeline, reducing unnecessary Blender launches.

- Phase 1 Verification Report
  Automated Tests: Fast suite passed in 1.55s (144 tests).
  Manual Verification: Slow suite passed in 217s (9 tests).
  Changes: Successfully separated slow/fast tests using markers and directory structure.

- Task: Configure Pytest Markers
  Summary: Defined 'integration' marker in pyproject.toml and applied it to slow integration tests.
  Files: pyproject.toml, tests/integration/*.py
  Why: To allow filtering out slow tests during development.

- Task: Reorganize existing tests
  Summary: Moved slow integration tests to tests/integration/ and fast unit tests to tests/unit/.
  Files: tests/integration/, tests/unit/
  Why: To separate slow/fast tests and improve developer workflow.

- Task: Update CLI Error Catching
  Summary: Updated CLI to catch Pydantic ValidationError and print rich-formatted error messages. Added unit test.
  Files: cli.py, tests/unit/test_cli_validation.py
  Why: To provide user-friendly feedback on configuration errors.

- Phase 3 Verification Report
  Automated Tests: Passed (pytest).
  Manual Verification: Verified speed of --skip-render (~1s for 10 scenes).
  Changes: Optimized test suite, enabled --skip-render CLI flag.

- Task: Verification & Benchmarking
  Summary: Optimized reproducibility tests by adding --skip-render flag to CLI and using tiny resolutions for pixel-identical checks. Enabled deterministic random seeds in the backend executor.
  Files: cli.py, backend/executor.py, tests/test_reproducibility.py
  Why: To provide fast and reliable verification of scientific reproducibility.

- Phase 2 Verification Report
  Automated Tests: Passed (pytest).
  Manual Verification: Generated scene and verified sidecar JSON contains correct git hash (b4e477b).
  Changes: Implemented git hash utility, SceneProvenance schema, SidecarWriter, and backend integration.

- Task: Integration Test - Provenance Chain
  Summary: Implemented end-to-end integration test verifying sidecar generation. Refactored SidecarWriter and executor.py to avoid Pydantic dependencies in Blender environment.
  Files: backend/executor.py, data_io/writers.py, tests/test_provenance_integration.py
  Why: To verify metadata provenance is robustly captured in the production pipeline.

- Task: Implement Sidecar Writer
  Summary: Implemented SidecarWriter in data_io/writers.py and integrated it into backend/executor.py to write JSON sidecars with provenance metadata for each generated image.
  Files: backend/executor.py, data_io/writers.py, tests/unit/test_sidecar_writer.py
  Why: To ensure every generated image has traceable origin data.

- Task: Update Sidecar Schema
  Summary: Added SceneProvenance Pydantic model to schema.py to structure sidecar metadata.
  Files: schema.py, tests/unit/test_provenance_schema.py
  Why: To define the contract for provenance data.

- Task: Git Hash Retrieval Utility
  Summary: Implemented get_git_hash function in common/git.py to retrieve current commit hash for provenance.
  Files: common/git.py, tests/unit/test_git_utils.py
  Why: To tag generated datasets with the exact code version used.

- Phase 1 Verification Report
  Automated Tests: Passed (pytest).
  Manual Verification: Verified that two independent runs produce identical scene recipes using diff.
  Changes: Implemented SeedManager, updated Generator, ensured Sharding invariance.

- Task: Scene-Level Determinism
  Summary: Updated Generator to use SeedManager for deriving scene seeds from the master seed. Ensured sharding invariance by NOT overriding the seed per-shard.
  Files: generator.py, orchestration/sharding.py, tests/unit/test_generator_determinism.py
  Why: To ensure that Scene N is always identical regardless of how the job is sharded.

- Task: Integrate SeedManager into Sharding Logic
  Summary: Updated sharding.py to calculate shard seeds using SeedManager and pass them via --seed. Updated cli.py to accept --seed override.
  Files: orchestration/sharding.py, cli.py, tests/unit/test_sharding_seeds.py
  Why: To enforce strict seed hierarchy during parallel execution.

- Task: Implement SeedManager utility
  Summary: Created SeedManager class in common/math.py to handle deterministic sequential seed generation for shards. Added unit tests.
  Files: src/render_tag/common/math.py, tests/unit/test_seed_manager.py
  Why: To ensure reproducible dataset generation across shards.

- Phase 3 Verification Report
  Automated Tests: Passed (pytest)
  Manual Verification: Verified generation and visualization with Gaussian noise.
  Changes: Updated ShadowRenderer, added full pipeline test.

- Task: Full Pipeline Integration Test
  Summary: Added an end-to-end integration test that runs the full generation pipeline with all new industrial features enabled (noise, presets, surface imperfections). Validates output artifacts.
  Files: tests/test_industrial_pipeline.py
  Why: To ensure all new features work together correctly in the final build.

- Task: Update Shadow Render for New Features
  Summary: Updated ShadowRenderer to display sensor noise information in the 2D layout visualization. Added unit test.
  Files: visualization.py, tests/unit/test_visualization.py
  Why: To allow quick verification of sensor settings without rendering.

- Phase 2 Verification Report
  Automated Tests: Passed (pytest)
  Manual Verification: Verified generation using lighting_preset: factory.
  Changes: Implemented LightingPreset, TagSurfaceConfig, and backend assets stub.

- Task: Procedural Surface Imperfections
  Summary: Added TagSurfaceConfig to schema and implemented apply_surface_imperfections stub in backend/assets.py. Verified imports with unit tests.
  Files: schema.py, backend/assets.py, tests/unit/test_surface_imperfections.py
  Why: To simulate realistic wear and tear on tags.

- Task: Industrial HDRi Lighting Presets
  Summary: Implemented LightingPreset enum and logic in config.py to easily configure lighting intensity and radius for industrial scenarios. Added unit tests.
  Files: config.py, tests/unit/test_lighting_presets.py
  Why: To provide realistic lighting defaults for different environments.

- Phase 1 Verification Report
  Automated Tests: Passed (pytest)
  Manual Verification: Verified generation of noisy images with new parametric noise config.
  Changes: Implemented SensorNoiseConfig, updated backend generator and executor, verified end-to-end flow.

- Task: Refine Procedural Motion Blur
  Summary: Moved motion blur logic from executor.py to backend/camera.py for better separation of concerns. Verified API existence with unit test.
  Files: backend/camera.py, backend/executor.py, tests/unit/test_motion_blur_logic.py
  Why: To centralize camera-related logic and make it reusable.

- Task: Implement Parametric Sensor Noise Models
  Summary: Added SensorNoiseConfig to schema, implemented noise generation logic in backend/sensors.py, and integrated it into the executor.
  Files: schema.py, backend/sensors.py, backend/executor.py, tests/unit/test_sensor_noise_model.py
  Why: To allow more realistic sensor simulation for industrial scenarios.


