import sys
import pytest
import subprocess
from pathlib import Path
from pytest_mock import MockerFixture
from pyunslop.ruff import check_ruff
from collections.abc import Callable
from importlib.resources import files


@pytest.fixture
def write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str, str], Path]:
    """Create source files outside the checkout to verify project-local configuration."""
    monkeypatch.chdir(tmp_path)

    def write_file(filename: str, source: str) -> Path:
        """Keep fixture filenames relative to the scanned project."""
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    return write_file


SUPPRESSION_SOURCES = ("import os  # noqa\n", "import os  # noqa: F401\n", "# ruff: noqa\nimport os\n", "# flake8: noqa\nimport os\n")


def test_lint_and_format_are_warnings_without_edits(write: Callable[[str, str], Path]) -> None:
    """Report lint and formatting diagnostics while retaining source bytes."""
    source = "import os\nvalue=1\n"
    path = write("example.py", source)
    warnings = check_ruff([path])
    assert {"F401", "RFMT001"} <= {warning.code for warning in warnings}
    assert path.read_text() == source
    assert all("warning:" in str(warning) for warning in warnings)
    assert not Path(".ruff_cache").exists()


def test_tests_ignores_are_relative_to_scanned_project(write: Callable[[str, str], Path]) -> None:
    """Keep security exemptions limited to the scanned project's tests tree."""
    production = write("example.py", "assert True\n")
    test = write("tests/test_example.py", "assert True\n")
    warnings = check_ruff([production, test])
    assert any(warning.code == "S101" and warning.path.name == "example.py" for warning in warnings)
    assert not any(warning.code == "S101" and warning.path.name == "test_example.py" for warning in warnings)


def test_argument_and_name_ignores_apply_only_to_tests(write: Callable[[str, str], Path]) -> None:
    """Apply ARG and N803 exemptions without disabling them for production code."""
    source = 'def helper(Unused):\n    """Return a constant."""\n    return 1\n'
    production = write("example.py", source)
    test = write("tests/test_example.py", source)
    warnings = check_ruff([production, test])
    assert {"ARG001", "N803"} <= {warning.code for warning in warnings if warning.path.name == "example.py"}
    assert not any(warning.code in {"ARG001", "N803"} and warning.path.name == "test_example.py" for warning in warnings)


def test_file_names_cannot_be_interpreted_as_flags(write: Callable[[str, str], Path]) -> None:
    """Pass explicit filenames after the command-line option terminator."""
    source = "value=1\n"
    path = write("--fix.py", source)
    assert any(warning.code == "RFMT001" for warning in check_ruff([path]))
    assert path.read_text() == source


def test_project_configuration_cannot_disable_fixed_rules(write: Callable[[str, str], Path]) -> None:
    """Ignore local Ruff configuration when running the bundled preset."""
    write("ruff.toml", "fix = true\n[lint]\nselect = []\n")
    path = write("example.py", "import os\n")
    assert any(warning.code == "F401" for warning in check_ruff([path]))
    assert path.read_text() == "import os\n"


@pytest.mark.parametrize("source", SUPPRESSION_SOURCES)
def test_noqa_cannot_hide_ruff_findings(write: Callable[[str, str], Path], source: str) -> None:
    """Ignore inline and file-wide suppressions when running the fixed preset."""
    path = write("example.py", source)
    assert "F401" in {warning.code for warning in check_ruff([path])}
    assert path.read_text() == source


def test_noqa_and_underlying_warning_are_advisory(write: Callable[[str, str], Path]) -> None:
    """Report the directive and hidden violation together without editing files."""
    source = "import os  # noqa: F401\n"
    path = write("example.py", source)
    result = subprocess.run([sys.executable, "-m", "pyunslop"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "warning: CM004" in result.stdout
    assert "warning: F401" in result.stdout
    assert path.read_text() == source


def test_local_ruff_module_is_never_executed(write: Callable[[str, str], Path]) -> None:
    """Invoke the installed binary instead of importing inspected Python code."""
    write("ruff.py", 'raise RuntimeError("inspected code executed")\n')
    path = write("example.py", "import os\n")
    assert any(warning.code == "F401" for warning in check_ruff([path]))
    result = subprocess.run([sys.executable, "-m", "pyunslop"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "inspected code executed" not in result.stderr


def test_format_uses_fixed_line_length_and_trailing_comma_policy(write: Callable[[str, str], Path]) -> None:
    """Honor the supplied formatter settings rather than Ruff defaults."""
    source = "value = combine(" + ", ".join(f"argument_{index}" for index in range(8)) + ")\n"
    path = write("example.py", source)
    assert not any(warning.code == "RFMT001" for warning in check_ruff([path]))
    path.write_text("value = combine(\n    first,\n    second,\n)\n")
    assert any(warning.code == "RFMT001" for warning in check_ruff([path]))


def test_missing_annotations_are_warning_only(write: Callable[[str, str], Path]) -> None:
    """Require argument and return annotations without failing the CLI."""
    source = 'def greet(name):\n    """Return the supplied name."""\n    return name\n'
    path = write("example.py", source)
    assert {"ANN001", "ANN201"} <= {warning.code for warning in check_ruff([path])}
    result = subprocess.run([sys.executable, "-m", "pyunslop"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "warning: ANN001" in result.stdout
    assert "warning: ANN201" in result.stdout
    assert path.read_text() == source


def test_explicit_any_annotations_remain_flagged(write: Callable[[str, str], Path]) -> None:
    """Retain ANN401 when enabling the complete annotation rule family."""
    source = 'from typing import Any\ndef echo(value: Any) -> Any:\n    """Return the supplied value."""\n    return value\n'
    path = write("example.py", source)
    assert any(warning.code == "ANN401" for warning in check_ruff([path]))


def test_complete_annotations_are_accepted(write: Callable[[str, str], Path]) -> None:
    """Avoid annotation findings for fully typed functions."""
    source = 'def greet(name: str) -> str:\n    """Return the supplied name."""\n    return name\n'
    path = write("example.py", source)
    assert not any(warning.code.startswith("ANN") for warning in check_ruff([path]))


def test_syntax_errors_remain_warnings(write: Callable[[str, str], Path]) -> None:
    """Treat Ruff parse diagnostics as findings rather than operational failures."""
    path = write("example.py", "def broken(\n")
    assert check_ruff([path])


def test_no_files_does_not_scan_the_current_directory(write: Callable[[str, str], Path], mocker: MockerFixture) -> None:
    """Avoid Ruff's implicit directory scan when the input set is empty."""
    write("example.py", "import os\n")
    run = mocker.patch("pyunslop.ruff.subprocess.run")
    assert check_ruff([]) == []
    run.assert_not_called()


def test_cli_runs_ruff_and_still_exits_successfully(write: Callable[[str, str], Path]) -> None:
    """Run the real module entry point with findings from both engines."""
    source = "import os\nvalue=1\n"
    path = write("example.py", source)
    result = subprocess.run([sys.executable, "-m", "pyunslop"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "warning: F401" in result.stdout
    assert "warning: RFMT001" in result.stdout
    assert path.read_text() == source


def test_operational_failure_does_not_report_success(write: Callable[[str, str], Path], mocker: MockerFixture) -> None:
    """Distinguish an unavailable Ruff engine from ordinary lint findings."""
    path = write("example.py", "value = 1\n")
    failed = subprocess.CompletedProcess([], 2, "", "Ruff unavailable")

    # Nonzero exits without diagnostics must not be mistaken for ordinary findings.
    mocker.patch("pyunslop.ruff.subprocess.run", return_value=failed)
    with pytest.raises(RuntimeError, match="Ruff unavailable"):
        check_ruff([path])


def test_bundled_preset_matches_development_configuration() -> None:
    """Keep the wheel's preset synchronized with the requested pyproject tables."""
    preset = files("pyunslop").joinpath("ruff.toml").read_text(encoding="utf-8")
    project = Path(__file__).resolve().parents[1].joinpath("pyproject.toml").read_text(encoding="utf-8")
    expected = "[tool.ruff]\n" + preset.replace("\n[", "\n[tool.ruff.")
    assert project.endswith(expected)
