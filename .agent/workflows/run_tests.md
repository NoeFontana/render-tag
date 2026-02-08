---
description: Run the project's test suite
---

# Run Tests

Execute the comprehensive test suite to ensure stability.

1.  **Run All Tests**
    Runs all unit and integration tests.
    ```bash
    uv run pytest
    ```

2.  **Run Fast Tests Only**
    Skips slow integration or data-heavy tests.
    ```bash
    uv run pytest -m "not slow"
    ```

3.  **Run Specific Test File**
    Replace `tests/unit/test_example.py` with your target file.
    ```bash
    uv run pytest tests/unit/test_example.py
    ```
