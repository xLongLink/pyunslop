import pytest
from tests.support import RunCLI, CheckNative, native_codes


def test_clean_project_exits_successfully(run_cli: RunCLI) -> None:
    """Exercise discovery, native checks, Ruff lint, formatting, and module exit."""

    # Arrange
    sources = {"nested/example.py": "value = 1\n", ".venv/dependency.py": "# noqa\n"}

    # Act
    result = run_cli(sources)

    # Assert
    assert (result.returncode, result.stdout, result.stderr) == (0, "All checks passed!\n", "")


def test_native_and_ruff_findings_share_a_sorted_report(run_cli: RunCLI) -> None:
    """Use the fixed preset even if project settings disable every Ruff rule."""

    # Arrange
    sources = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["ALL"]\n', "example.py": "import os\n\n# noqa: SLOP003\nvalue=1\n"}

    # Act
    result = run_cli(sources)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP003"]
    assert result.stdout.splitlines() == [
        "example.py:1:8: F401 `os` imported but unused",
        "example.py:3:1: SLOP003 noqa suppression directives are forbidden",
        "example.py:4:6: unformatted File would be reformatted",
        "Found 3 errors.",
    ]


@pytest.mark.parametrize("argument", ["--max-lines", "--repo-policy", "example.py"])
def test_rejects_arguments_and_obsolete_flags(run_cli: RunCLI, argument: str) -> None:
    """The fixed-preset CLI accepts no flags or explicit paths."""

    # Act
    result = run_cli("value = 1\n", argument)

    # Assert
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "pyunslop takes no arguments; run it from your project directory.\n"


def test_invalid_source_does_not_hide_findings_in_other_files(run_cli: RunCLI) -> None:
    """Real Ruff syntax errors and valid native findings both reach the report."""

    # Arrange
    sources = {"broken.py": "def broken(\n", "valid.py": "# noqa\nvalue=1\n"}

    # Act
    result = run_cli(sources)

    # Assert
    assert result.returncode == 1
    assert result.stderr == ""
    assert "broken.py:" in result.stdout
    assert result.stdout.count(": invalid-syntax ") == 1
    assert "valid.py:1:1: SLOP003" in result.stdout
    assert "valid.py:2:6: unformatted" in result.stdout


def test_syntax_errors_are_lint_findings_not_execution_failures(run_cli: RunCLI) -> None:
    """Normalize Ruff's null syntax code and deduplicate lint/formatter reports."""

    # Act
    result = run_cli("def broken(\n")

    # Assert
    assert (result.returncode, result.stderr) == (1, "")
    assert result.stdout.splitlines() == ["example.py:2:1: invalid-syntax unexpected EOF while parsing", "Found 1 error."]


def test_unrepresentable_filenames_remain_execution_failures(run_cli: RunCLI) -> None:
    """Keep operational failures distinct from successfully collected findings."""

    # Arrange
    sources = {"first\nsecond.py": "value = 1\n"}

    # Act
    result = run_cli(sources)

    # Assert
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Could not scan project:" in result.stderr
    assert "newline-containing" in result.stderr.lower()


@pytest.mark.parametrize(
    "source",
    [
        "value=1\n",
        "# noqa\nvalue = 1\n",
        "from sqlalchemy.engine import Result\ndef consume(result: Result):\n    é = 1; rows = list(result.all())\n",
    ],
)
def test_direct_native_checks_match_cli_diagnostics(check_native: CheckNative, run_cli: RunCLI, source: str) -> None:
    """Preserve native messages and coordinates when bypassing CLI integration."""
    findings = check_native(source)

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == [finding.code for finding in findings]
    assert [line for line in result.stdout.splitlines() if ": SLOP" in line] == [
        f"{finding.path.name}:{finding.line}:{finding.column}: {finding.code} {finding.message}" for finding in findings
    ]


@pytest.mark.parametrize("source", ["def broken(\n", "return 1\n", "rows = [item for item in (value := items)]\n"])
def test_direct_native_fixture_rejects_invalid_sources(check_native: CheckNative, source: str) -> None:
    """Do not let malformed native-rule fixtures silently pass as clean files."""
    with pytest.raises(SyntaxError):
        check_native(source)
