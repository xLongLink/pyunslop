import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize("directive", ["# noqa", "# noqa: F401", "# NoQa: SLOP003", "# ruff: noqa", "# flake8: noqa: F401"])
def test_suppression_cannot_hide_native_findings(run_cli: RunCLI, directive: str) -> None:
    """Reject bare, code-specific, file-wide, and mixed-case suppression tokens."""

    # Arrange
    source = f"import os  {directive}\nvalue = 1\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP003"]
    assert "noqa suppression directives are forbidden" in result.stdout


@pytest.mark.parametrize("source", ["value = 1\n", 'text = "# noqa: F401"\n', "# Explain noqa conventions.\n# noqaish\nvalue = 1\n"])
def test_strings_and_ordinary_comments_are_not_directives(run_cli: RunCLI, source: str) -> None:
    """Accept the documented fix and literal or prose mentions of suppression."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
    assert result.returncode == 0, result.stdout
