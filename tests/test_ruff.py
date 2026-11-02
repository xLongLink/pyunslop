import json
import pytest
import subprocess
from pathlib import Path
from pyunslop import ruff
from unittest.mock import Mock
from pyunslop.diagnostics import Diagnostic


@pytest.fixture
def syntax_diagnostic() -> dict[str, object]:
    """Represent Ruff's null-code lint syntax error using a project-local path."""
    return {
        "filename": str(Path.cwd() / "broken.py"),
        "code": None,
        "name": "invalid-syntax",
        "message": "unexpected EOF while parsing",
        "location": {"row": 2, "column": 1},
    }


@pytest.mark.parametrize("output", ["not json", "{}", "[null]", "[{}]"])
def test_invalid_ruff_output_remains_an_execution_failure(monkeypatch: pytest.MonkeyPatch, output: str) -> None:
    """Reject invalid JSON and diagnostic schemas rather than reporting success."""
    result = subprocess.CompletedProcess([], 0, output, "")
    monkeypatch.setattr(ruff.subprocess, "run", Mock(return_value=result))

    # Act / Assert
    with pytest.raises(RuntimeError, match="Ruff returned invalid diagnostics"):
        ruff.check_ruff()


@pytest.mark.parametrize("location", [None, {"row": True, "column": 1}, {"row": 0, "column": 1}, {"row": 1, "column": "1"}])
def test_invalid_coordinates_remain_execution_failures(
    monkeypatch: pytest.MonkeyPatch, syntax_diagnostic: dict[str, object], location: object
) -> None:
    """Require positive integer coordinates, excluding booleans and numeric strings."""
    syntax_diagnostic["location"] = location
    result = subprocess.CompletedProcess([], 1, json.dumps([syntax_diagnostic]), "")
    monkeypatch.setattr(ruff.subprocess, "run", Mock(return_value=result))

    # Act / Assert
    with pytest.raises(RuntimeError, match="Ruff returned invalid diagnostics"):
        ruff.check_ruff()


def test_syntax_diagnostics_are_normalized_and_deduplicated(monkeypatch: pytest.MonkeyPatch, syntax_diagnostic: dict[str, object]) -> None:
    """Merge identical lint and formatter reports into one public diagnostic."""
    result = subprocess.CompletedProcess([], 1, json.dumps([syntax_diagnostic]), "")
    monkeypatch.setattr(ruff.subprocess, "run", Mock(return_value=result))

    # Act
    findings = ruff.check_ruff()

    # Assert
    assert findings == [Diagnostic(Path("broken.py"), 2, 1, "invalid-syntax", "unexpected EOF while parsing")]


def test_formatter_syntax_status_preserves_text_output(monkeypatch: pytest.MonkeyPatch, syntax_diagnostic: dict[str, object]) -> None:
    """Allow formatter status two only for validated syntax diagnostics without stderr."""
    output = json.dumps([syntax_diagnostic])
    result = subprocess.CompletedProcess([], 2, output, "")
    monkeypatch.setattr(ruff.subprocess, "run", Mock(return_value=result))

    # Act / Assert
    assert ruff.run_ruff("format", "--check") == output


def test_formatter_validates_entries_after_a_syntax_error(monkeypatch: pytest.MonkeyPatch, syntax_diagnostic: dict[str, object]) -> None:
    """A valid syntax diagnostic must not hide a later malformed entry."""
    result = subprocess.CompletedProcess([], 2, json.dumps([syntax_diagnostic, {}]), "")
    monkeypatch.setattr(ruff.subprocess, "run", Mock(return_value=result))

    # Act / Assert
    with pytest.raises(RuntimeError, match="Ruff failed:"):
        ruff.run_ruff("format", "--check")


def test_formatter_stderr_preserves_execution_failure(monkeypatch: pytest.MonkeyPatch, syntax_diagnostic: dict[str, object]) -> None:
    """Do not reinterpret formatter execution errors as ordinary syntax findings."""
    result = subprocess.CompletedProcess([], 2, json.dumps([syntax_diagnostic]), "formatter failed")
    monkeypatch.setattr(ruff.subprocess, "run", Mock(return_value=result))

    # Act / Assert
    with pytest.raises(RuntimeError, match="Ruff failed: formatter failed"):
        ruff.run_ruff("format", "--check")
