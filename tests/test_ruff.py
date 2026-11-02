import json
import pytest
import subprocess
from pathlib import Path
from pytest_mock import MockerFixture
from pyunslop.ruff import TIMEOUT_SECONDS, check_ruff


def test_ruff_checks_lint_and_format_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Use the bundled preset even when project settings disable lint rules."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["ALL"]\n')
    path = tmp_path / "example.py"
    source = "import os\nvalue=1\n"
    path.write_text(source)

    # Both checks must report findings despite the project's disabled rules.
    findings = check_ruff()
    assert any(item.code == "F401" and "`os` imported but unused" in item.message for item in findings)
    assert any(item.code == "unformatted" for item in findings)
    assert all(item.path == Path("example.py") for item in findings)
    assert capsys.readouterr() == ("", "")
    assert path.read_text() == source


def test_clean_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Keep successful checks quiet for the CLI's shared success summary."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("value = 1\n")
    assert not check_ruff()
    assert capsys.readouterr() == ("", "")


def test_markdown_examples_are_not_formatted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Preserve intentionally bad documentation examples without hiding Python findings."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    markdown = tmp_path / "docs" / "example.md"
    source = "# Example\n\n```python\nvalue=1\n```\n"
    markdown.write_text(source)
    (tmp_path / "example.py").write_text("value=1\n")
    findings = check_ruff()

    # Only actual Python source should contribute formatting diagnostics.
    assert [(item.code, item.path) for item in findings] == [("unformatted", Path("example.py"))]
    assert markdown.read_text() == source


def test_operational_failure(mocker: MockerFixture) -> None:
    """Do not treat Ruff invocation errors as ordinary findings."""
    mocker.patch("pyunslop.ruff.subprocess.run", return_value=subprocess.CompletedProcess([], 2, "", "invalid configuration"))
    with pytest.raises(RuntimeError, match="invalid configuration"):
        check_ruff()


def test_timeout_is_an_operational_failure(mocker: MockerFixture) -> None:
    """Bound Ruff execution without waiting for a real process to time out."""
    run = mocker.patch("pyunslop.ruff.subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", TIMEOUT_SECONDS))
    with pytest.raises(RuntimeError, match="Ruff timed out"):
        check_ruff()
    assert run.call_args.kwargs["timeout"] == TIMEOUT_SECONDS


def test_ast_visitor_names_are_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow visitor methods and aliases without disabling other naming checks."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "visitor.py").write_text(
        "import ast\n"
        "class Visitor(ast.NodeVisitor):\n"
        "    def visit_FunctionDef(self, node):\n"
        "        pass\n"
        "    visit_AsyncFunctionDef = visit_FunctionDef\n"
        "    def BadMethod(self):\n"
        "        pass\n"
        "    badAlias = BadMethod\n"
    )

    # Only the visitor convention is exempt; ordinary mixed-case names still fail.
    findings = [item for item in check_ruff() if item.code in {"N802", "N815"}]
    assert [(item.code, item.line) for item in findings] == [("N802", 6), ("N815", 8)]


def test_invalid_output_is_an_operational_failure(mocker: MockerFixture) -> None:
    """Reject malformed output rather than claiming that the project is clean."""
    mocker.patch("pyunslop.ruff.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "not JSON", ""))
    with pytest.raises(RuntimeError, match="invalid diagnostics"):
        check_ruff()


@pytest.mark.parametrize("payload", [None, {}, "", [None], [1], [[]], [{}]])
def test_invalid_response_shapes_are_rejected(mocker: MockerFixture, payload: object) -> None:
    """Require an array of diagnostic objects rather than arbitrary valid JSON."""
    mocker.patch("pyunslop.ruff.run_ruff", return_value=json.dumps(payload))
    with pytest.raises(RuntimeError, match="invalid diagnostics"):
        check_ruff()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("filename", None),
        ("filename", "relative.py"),
        ("code", 1),
        ("code", ""),
        ("message", []),
        ("location", None),
        ("location", {}),
        ("location", {"row": 0, "column": 1}),
        ("location", {"row": 1, "column": -1}),
        # Booleans are integers in Python, but not valid source coordinates.
        ("location", {"row": True, "column": 1}),
        ("location", {"row": 1, "column": "2"}),
        ("location", {"row": 1.5, "column": 1}),
    ],
)
def test_invalid_diagnostic_fields_are_rejected(mocker: MockerFixture, field: str, value: object) -> None:
    """Reject values that would break location sorting or diagnostic rendering."""
    diagnostic = {
        "filename": str(Path.cwd() / "example.py"),
        "code": "F401",
        "message": "Unused import",
        "location": {"row": 1, "column": 1},
    }

    # Change one field of an otherwise valid response.
    diagnostic[field] = value
    mocker.patch("pyunslop.ruff.run_ruff", return_value=json.dumps([diagnostic]))
    with pytest.raises(RuntimeError, match="invalid diagnostics"):
        check_ruff()
