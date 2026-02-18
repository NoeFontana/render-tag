# Specification: Subject Strategy Pattern (Compiler Refactor)

## Overview
This track implements the "Subject Strategy" pattern to decouple the `SceneCompiler` from domain-specific object logic (Tags vs. Boards). By introducing a unified `SubjectStrategy` protocol, the compiler becomes agnostic to the specific content being rendered, enabling future subject types to be added without modifying the core compilation loop.

## Functional Requirements
1.  **SubjectStrategy Interface (Protocol):**
    -   Define a `typing.Protocol` with two primary methods:
        -   `prepare_assets(context: GenerationContext)`: Registers necessary textures, meshes, and materials in the asset management layer.
        -   `sample_pose(seed: int, context: GenerationContext) -> list[ObjectRecipe]`: Generates a list of positioned objects for a single scene.
2.  **TagStrategy Implementation:**
    -   Refactor existing "Flying Tag" logic from `compiler.py`, `tag_gen.py`, and `layouts.py` into this strategy.
    -   Utilize composition/delegation best practices to orchestrate scattering and collision checks.
3.  **BoardStrategy Implementation:**
    -   Implement the "Single-Plane Board" logic.
    -   **Asset Preparation:** Integrate `texture_factory.py` to generate and cache board textures.
    -   **Pose Sampling:** Return a single `ObjectRecipe` representing a standard 1x1 unit plane scaled to the board's physical dimensions `(width_m, height_m, 1)`.
4.  **Strategy Factory (Dependency Injection):**
    -   Implement `get_subject_strategy(config: ScenarioConfig)` to return the appropriate strategy based on the polymorphic `subject` discriminator.
5.  **Agnostic Compiler Refactor:**
    -   Remove type-specific checks (`if board: ...`) from `SceneCompiler.compile_scenes`.
    -   Plumb the strategy into the main loop to handle asset preparation (once per job) and pose sampling (per scene).

## Non-Functional Requirements
-   **Strict Separation of Concerns:** The `SceneCompiler` must not contain any logic specific to "Tags" or "Boards."
-   **Testability:** Strategies must be unit-testable in isolation using mocks for the `GenerationContext`.
-   **Performance:** Asset preparation (e.g., texture synthesis) should only happen once per job using the established hashing/caching mechanism.

## Acceptance Criteria
-   `SceneCompiler` contains no `if/else` logic switching between board and tag modes.
-   Both "Flying Tag" and "Calibration Board" scenarios can be rendered successfully using the same compilation loop.
-   `BoardStrategy` correctly scales a unit plane to match the `BoardConfig` geometry.
-   All existing and new unit tests for the compiler and strategies pass with >80% coverage.

## Out of Scope
-   Extending the backend renderer logic (Focus is strictly on the Host-side compiler layer).
-   Implementation of complex 3D subjects (e.g., CAD models).
