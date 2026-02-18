# Specification: Polymorphic Subject Architecture (Phase 1)

## Overview
The goal of this track is to implement a polymorphic "Subject" abstraction in the configuration and schema layers. This allows the system to be agnostic about whether it is rendering a collection of "Flying Tags" or a single "Calibration Board," moving towards a "Pure Executor" backend model where domain-specific logic resides on the Host.

## Functional Requirements
1.  **Polymorphic Schema (Pydantic v2):**
    -   Isolate tag-related parameters into `TagSubjectConfig` (`type: "TAGS"`).
    -   Isolate board-related parameters into `BoardSubjectConfig` (`type: "BOARD"`).
    -   Replace loose fields in `ScenarioConfig` with a `subject` field using a Pydantic `Discriminated Union`.
2.  **Agnostic Backend Interface (Host-Side Decompositon):**
    -   Update the `SceneCompiler` to decompose any `Subject` into generic primitives: a plane mesh, a texture path, and a standardized list of 3D keypoints for ground-truth projection.
3.  **Standardized Data Export:**
    -   Ensure `COCOWriter`, `CSVWriter`, and `RichTruthWriter` handle the unified `Subject` outputs correctly.
    -   Maintain strict COCO compliance for keypoints and categories.
4.  **Strict Schema Versioning:**
    -   Increment the global `schema_version`.
    -   Support the new polymorphic `subject` structure only for the new version.
    -   Legacy configs must be manually updated to the new version/structure (no implicit mapping).

## Non-Functional Requirements
-   **Type Safety:** Enforce strict typing across the Host-to-Backend boundary using the new schema.
-   **Reproducibility:** Ensure the cryptographic fingerprinting (SHA256) of the new polymorphic `ObjectRecipe` is deterministic.

## Acceptance Criteria
-   `ScenarioConfig` successfully validates both "TAGS" and "BOARD" subject types from YAML.
-   The Blender backend renders a "BOARD" or "TAGS" using the same unified `ObjectRecipe` structure.
-   Sub-pixel ground truth is correctly exported for both types using the standardized keypoint list.
-   Existing tests for legacy configs fail gracefully or require version updates, confirming strict version enforcement.

## Out of Scope
-   Automatic migration of legacy YAML files (Migration script/manual update required).
-   Implementation of non-planar subjects (e.g., 3D cubes or custom models).
