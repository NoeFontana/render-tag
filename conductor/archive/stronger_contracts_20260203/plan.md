# Implementation Plan - Architecture: Stronger Contracts

This plan refactors the data layer from `dataclasses` to Pydantic v2 to ensure robust validation and easier serialization.

## Phase 1: Core Schema Migration (`schema.py`)
**Goal:** Establish the contract between the generator and renderer using Pydantic.

- [~] Task: Migrate `src/render_tag/schema.py`
    - [ ] Replace `@dataclass` with Pydantic `BaseModel`.
    - [ ] Update field definitions with `Field` constraints (e.g., `min_length`, `ge`).
    - [ ] Verify serialization using `model_dump(mode='json')`.
- [ ] Task: Update Backend Parsers
    - [ ] Update `src/render_tag/backend/executor.py` to handle the dictionary format produced by Pydantic serialization (if necessary, though it's already using `json.load`).
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Core Schema Migration' (Protocol in workflow.md)

## Phase 2: Configuration Migration (`config.py`)
**Goal:** Implement strict validation for user-provided YAML configs.

- [ ] Task: Migrate `src/render_tag/config.py`
    - [ ] Convert `GenConfig` and nested configs to Pydantic models.
    - [ ] Implement `field_validator` for ranges (e.g., `intensity_min <= intensity_max`).
    - [ ] Ensure `TagFamily` Enum integrates correctly with Pydantic.
- [ ] Task: Update Configuration Loader
    - [ ] Update `load_config` in `config.py` to use `GenConfig.model_validate(yaml_data)`.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Configuration Migration' (Protocol in workflow.md)

## Phase 3: CLI & Error Handling Integration
**Goal:** Provide user-friendly feedback for configuration errors.

- [~] Task: Update CLI Error Catching
    - [ ] In `src/render_tag/cli.py`, wrap config loading in `try/except ValidationError`.
    - [ ] Format the error output using `rich` to highlight the specific field and reason for failure.
- [ ] Task: Integration Test - Validation Failures
    - [ ] Create a test case that provides an invalid YAML and verifies the CLI output contains the expected error message.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: CLI & Error Handling Integration' (Protocol in workflow.md)

## Phase 4: Final Cleanup & Testing
**Goal:** Ensure full system integrity.

- [x] Task: Run Full Test Suite 48a73fa
    - [ ] Execute all unit and integration tests (`pytest`).
    - [ ] Fix any regressions caused by the API change from dataclasses to Pydantic models (e.g., accessing fields as attributes vs keys).
- [x] Task: Remove Dataclass Imports 48a73fa
    - [ ] Remove `from dataclasses import dataclass` from all migrated files.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Final Cleanup & Testing' (Protocol in workflow.md)
