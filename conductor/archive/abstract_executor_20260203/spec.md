# Specification - Infrastructure: Abstracting the Render Executor

## Overview
Rendering synthetic data is a compute-intensive task that varies significantly between local development and large-scale production runs. Currently, the system is hardcoded to use a local subprocess for rendering. This track refactors the execution logic into a pluggable "Executor" architecture, enabling users to seamlessly switch between local execution, containerized runs (Docker), and future cloud-based batch systems.

## Functional Requirements
- **Executor Protocol:**
    - Define a `RenderExecutor` Protocol in `src/render_tag/orchestration/executors.py`.
    - Standardize the `execute(recipe_path: Path, output_dir: Path, renderer_mode: str, shard_id: str)` method.
- **Pluggable Implementations:**
    - **LocalExecutor:** Re-implements the existing `subprocess.run` logic for local BlenderProc execution.
    - **DockerExecutor:** Executes the render command inside a Docker container using a pre-built image. Handles mounting local volumes for recipes and output.
    - **MockExecutor:** A "no-op" executor that simulates a successful render for fast testing of the orchestration layer.
- **CLI Integration:**
    - Add a `--executor` (or `-e`) flag to the `render-tag generate` command with options: `local` (default), `docker`, `mock`.
- **Docker Image Configuration:**
    - Allow users to specify the Docker image and tag via environment variables or a default value in the `DockerExecutor`.

## Non-Functional Requirements
- **Loose Coupling:** The core generator logic should remain entirely unaware of which executor is being used.
- **Error Handling:** All executors must capture and report stdout/stderr from the render process correctly.
- **Maintainability:** Ensure that adding a new executor (e.g., AWS Batch) in the future requires minimal changes to the core CLI.

## Acceptance Criteria
- [ ] Running `render-tag generate --executor mock` completes instantly and produces no renders.
- [ ] Running `render-tag generate --executor local` produces the same output as the current system.
- [ ] `DockerExecutor` correctly launches a container and maps volumes for input/output.
- [ ] Switching executors via the CLI flag is verified with unit and integration tests.
