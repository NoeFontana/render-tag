---
trigger: always_on
---

# Coding Standards

## Technical Standards
1.  **Strict Typing**: All function signatures must have type hints. Use `typing` module or standard collections.
2.  **Pydantic V2**: Use Pydantic V2 for all configuration models and schemas.
3.  **Google Docstrings**: Maintain Google-style docstrings for all public functions and classes. Focus on *why* and *arguments*.
4.  **Testing**:
    - **Unit Tests**: Mock `subprocess.run` for CLI tests.
    - **Blender Tests**: Mock `blenderproc`/`bpy` for unit testing Blender scripts when running in the host environment.
    - **CI Safety**: Disable data-heavy tests in CI unless `LOCUS_DATA_DIR` is present.

## Staff Engineer Practices
1.  **Dependency Injection**: Explicitly pass dependencies (services, configs) into classes/functions. Avoid global state or hardcoded instantiations.
2.  **State Management**: Use `dataclasses` (frozen preferred) or Pydantic models for data containers. Keep state immutable where possible.
3.  **Functional Core**: Prefer pure functions for logic. Push side effects (I/O, random) to the system boundaries.
4.  **Resource Safety**: Always use context managers (`with` statements) for file I/O, locks, and connections.
5.  **Composition over Inheritance**: Build complex behavior by composing simple components, not by deep inheritance hierarchies.
6.  **Async I/O**: Use `async`/`await` for I/O-bound tasks (network, DB) to ensure scalability.
7.  **Robust Error Handling**: Define custom exception hierarchies. Catch specific errors; never use bare `except:`.
8.  **Structured Logging**: Use the project logger. Include context (e.g., `logger.info("Processing", extra={"file": f})`).

## Quality Gates
- **Linting**: Code must pass `uv run ruff check --fix .`
- **Formatting**: Code must pass `uv run ruff format .`
- **Type Checking**: Code must pass `uv run ty`