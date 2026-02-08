# Implementation Plan: Codebase Modernization

## Phase 1: Logging & Pydantic Optimization [checkpoint: Phase 1 complete]
- [x] Task: Centralize Logging
    - [x] Create `src/render_tag/common/logging.py` with standard config
    - [x] Replace `print` in `generator.py` and `sharding.py` with `logging`
- [x] Task: Pydantic V2 Best Practices
    - [x] Refactor `save_recipe_json` in `generator.py` to use `model_dump(mode="json")`
    - [x] Audit other `model_dump` / `json.loads` patterns
- [x] Task: Conductor - User Manual Verification 'Phase 1: Logging & Pydantic' (Protocol in workflow.md)

## Phase 2: RNG Isolation & Seed Optimization [checkpoint: Phase 2 complete]
- [x] Task: Optimize SeedManager
    - [x] Refactor `SeedManager.get_shard_seed` to use `hashlib.sha256` for O(1) seed generation
    - [x] Update tests to verify determinism
- [x] Task: Isolated RNGs in Generator
    - [x] Update `Generator` to use `random.Random` instances
    - [x] Update `Generator` to use `np.random.default_rng()`
    - [x] Propagate RNG instances to geometry helper functions (if needed)
- [x] Task: Conductor - User Manual Verification 'Phase 2: RNG Isolation' (Protocol in workflow.md)

## Phase 3: Cleanup & Standards [checkpoint: Phase 3 complete]
- [x] Task: Docstring & Type Hint Audit
    - [x] Ensure all public methods in `generator.py` have Google-style docstrings
    - [x] Verify all new code passes `ty` and `ruff`
- [x] Task: Conductor - User Manual Verification 'Phase 3: Cleanup' (Protocol in workflow.md)
