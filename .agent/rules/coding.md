# Coding Standards

## Technical Standards
1.  **Strict Typing**: All function signatures must have type hints. Use `typing` module or standard collections.
2.  **Pydantic V2**: Use Pydantic V2 for all configuration models and schemas.
3.  **Google Docstrings**: Maintain Google-style docstrings for all public functions and classes. Focus on *why* and *arguments*.
4.  **Testing**:
    - **Unit Tests**: Mock `subprocess.run` for CLI tests.
    - **Blender Tests**: Mock `blenderproc`/`bpy` for unit testing Blender scripts when running in the host environment.
    - **CI Safety**: Disable data-heavy tests in CI unless `LOCUS_DATA_DIR` is present.

## Quality Gates
- **Linting**: Code must pass `uv run ruff check --fix .`
- **Formatting**: Code must pass `uv run ruff format .`
- **Type Checking**: Code must pass `uv run ty`
