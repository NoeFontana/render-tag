# Track Specification: Polymorphic Subject Architecture

## Overview
This track implements Phase 2 of the \"Unlocking the Rendering Pipeline\" initiative. It refactors the rendering engine to adhere to the Open/Closed Principle by introducing a polymorphic subject architecture. The goal is to decouple the core rendering loop from specific subject types (TAG, BOARD), allowing for easy extension without modifying the engine facade.

## Functional Requirements
- **AssetBuilder Interface:** Define a strict `AssetBuilder` Protocol for structural subtyping.
  - Method: `build(self, recipe: ObjectRecipe) -> list[Any]` (where `Any` represents Blender objects/assets).
- **Concrete Builders:**
  - `TagBuilder`: Handles the creation of AprilTags, material setup, and metadata attachment.
  - `CalibrationBoardBuilder`: Handles the creation of calibration boards, material setup, and metadata attachment.
  - `NullBuilder`: A placeholder builder for testing and ensuring the interface is correctly implemented.
- **Asset Registry:**
  - Implement an automated discovery mechanism for registering builders (e.g., decorator-based registration).
  - The registry will map subject types to their corresponding `AssetBuilder` instances.
- **Engine Refactor:**
  - Deconstruct the monolithic `spawn_objects` loop in `engine.py`.
  - The new `spawn_objects` loop should look up the correct builder from the registry and invoke its `build` method.
  - If a builder is missing for a requested subject type, the engine must \"Fail Hard\" (log a critical error and halt).

## Non-Functional Requirements
- **Maintainability:** The engine should be \"closed to modification but open to extension.\"
- **Testability:** The use of Protocols and a registry should simplify unit testing for individual builders.
- **Performance:** Ensure that the registry lookup and dynamic building do not introduce significant overhead.

## Acceptance Criteria
- [ ] `AssetBuilder` Protocol is defined and documented.
- [ ] `TagBuilder` and `CalibrationBoardBuilder` are implemented and successfully refactored out of the engine.
- [ ] `NullBuilder` exists and is used in tests.
- [ ] The engine successfully uses the registry to spawn objects.
- [ ] Adding a new builder requires zero changes to `engine.py`.
- [ ] Missing builders trigger a fatal error as expected.

## Out of Scope
- Support for complex hierarchical assets beyond simple planes.
- Integration of external plugin loading from external files (beyond internal auto-discovery).
