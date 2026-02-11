---
description: Run the project's test suite
---

# Run Tests

Execute the comprehensive test suite to ensure stability.

1.  **Run All Tests (Fast Parallel)**
    Runs all unit and integration tests using multiple cores.
    ```bash
    uv run pytest -n auto
    ```

2.  **Run Fast Tests Only**
    Skips slow integration tests.
    ```bash
    uv run pytest -m "not integration"
    ```

3.  **Run with Coverage**
    Generates a coverage report.
    ```bash
    uv run pytest --cov=src/render_tag --cov-report=term-missing
    ```

3.  **Run Specific Test File**
    Replace `tests/unit/test_example.py` with your target file.
    ```bash
    uv run pytest tests/unit/test_example.py
    ```
