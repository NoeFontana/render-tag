import subprocess


def test_import_linter_contracts_pass():
    """Architectural boundaries (layers, host isolation, determinism, sibling
    independence) are encoded in pyproject.toml's [tool.importlinter] table.
    Any new violation must be either fixed in code or explicitly justified by
    relaxing the contract — this test catches both ends of that loop.
    """
    result = subprocess.run(["uv", "run", "lint-imports"], capture_output=True, text=True)

    assert result.returncode == 0, (
        f"import-linter reported broken contracts:\n{result.stdout}\n{result.stderr}"
    )
    assert "BROKEN" not in result.stdout, (
        f"import-linter output contained 'BROKEN':\n{result.stdout}"
    )
