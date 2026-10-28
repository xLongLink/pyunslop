import os
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest import mock
from importlib.resources import files
from pyunslop.ruff_checks import check_ruff


class RuffTests(unittest.TestCase):
    """Exercise the installed Ruff engine rather than mocking lint findings."""

    def setUp(self) -> None:
        """Use a project outside the package checkout to verify configuration roots."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)

    def write(self, filename: str, source: str) -> Path:
        """Create a source file in the temporary project."""
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def test_lint_and_format_are_warnings_without_edits(self) -> None:
        """Report lint and formatting diagnostics while retaining source bytes."""
        source = "import os\nvalue=1\n"
        path = self.write("example.py", source)
        warnings = check_ruff([path])
        assert {"F401", "RFMT001"} <= {warning.code for warning in warnings}
        assert path.read_text() == source
        assert all("warning:" in str(warning) for warning in warnings)
        assert not Path(".ruff_cache").exists()

    def test_tests_ignores_are_relative_to_scanned_project(self) -> None:
        """Keep security exemptions limited to the scanned project's tests tree."""
        production = self.write("example.py", "assert True\n")
        test = self.write("tests/test_example.py", "assert True\n")
        warnings = check_ruff([production, test])
        assert any(warning.code == "S101" and warning.path.name == "example.py" for warning in warnings)
        assert not any(warning.code == "S101" and warning.path.name == "test_example.py" for warning in warnings)

    def test_argument_and_name_ignores_apply_only_to_tests(self) -> None:
        """Apply ARG and N803 exemptions without disabling them for production code."""
        source = 'def helper(Unused):\n    """Return a constant."""\n    return 1\n'
        production = self.write("example.py", source)
        test = self.write("tests/test_example.py", source)
        warnings = check_ruff([production, test])
        assert {"ARG001", "N803"} <= {warning.code for warning in warnings if warning.path.name == "example.py"}
        assert not any(warning.code in {"ARG001", "N803"} and warning.path.name == "test_example.py" for warning in warnings)

    def test_file_names_cannot_be_interpreted_as_flags(self) -> None:
        """Pass explicit filenames after the command-line option terminator."""
        source = "value=1\n"
        path = self.write("--fix.py", source)
        assert any(warning.code == "RFMT001" for warning in check_ruff([path]))
        assert path.read_text() == source

    def test_project_configuration_cannot_disable_fixed_rules(self) -> None:
        """Ignore local Ruff configuration when running the bundled preset."""
        self.write("ruff.toml", "fix = true\n[lint]\nselect = []\n")
        path = self.write("example.py", "import os\n")
        assert any(warning.code == "F401" for warning in check_ruff([path]))
        assert path.read_text() == "import os\n"

    def test_local_ruff_module_is_never_executed(self) -> None:
        """Invoke the installed binary instead of importing inspected Python code."""
        self.write("ruff.py", 'raise RuntimeError("inspected code executed")\n')
        path = self.write("example.py", "import os\n")
        assert any(warning.code == "F401" for warning in check_ruff([path]))
        result = subprocess.run([sys.executable, "-m", "pyunslop"], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
        assert "inspected code executed" not in result.stderr

    def test_format_uses_fixed_line_length_and_trailing_comma_policy(self) -> None:
        """Honor the supplied formatter settings rather than Ruff defaults."""
        source = "value = combine(" + ", ".join(f"argument_{index}" for index in range(8)) + ")\n"
        path = self.write("example.py", source)
        assert not any(warning.code == "RFMT001" for warning in check_ruff([path]))
        path.write_text("value = combine(\n    first,\n    second,\n)\n")
        assert any(warning.code == "RFMT001" for warning in check_ruff([path]))

    def test_missing_annotations_are_warning_only(self) -> None:
        """Require argument and return annotations without failing the CLI."""
        source = 'def greet(name):\n    """Return the supplied name."""\n    return name\n'
        path = self.write("example.py", source)
        assert {"ANN001", "ANN201"} <= {warning.code for warning in check_ruff([path])}
        result = subprocess.run([sys.executable, "-m", "pyunslop"], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
        assert "warning: ANN001" in result.stdout
        assert "warning: ANN201" in result.stdout
        assert path.read_text() == source

    def test_explicit_any_annotations_remain_flagged(self) -> None:
        """Retain ANN401 when enabling the complete annotation rule family."""
        source = 'from typing import Any\ndef echo(value: Any) -> Any:\n    """Return the supplied value."""\n    return value\n'
        path = self.write("example.py", source)
        assert any(warning.code == "ANN401" for warning in check_ruff([path]))

    def test_complete_annotations_are_accepted(self) -> None:
        """Avoid annotation findings for fully typed functions."""
        source = 'def greet(name: str) -> str:\n    """Return the supplied name."""\n    return name\n'
        path = self.write("example.py", source)
        assert not any(warning.code.startswith("ANN") for warning in check_ruff([path]))

    def test_package_exposes_its_type_information(self) -> None:
        """Ship the PEP 561 marker used by downstream static type checkers."""
        assert files("pyunslop").joinpath("py.typed").is_file()

    def test_syntax_errors_remain_warnings(self) -> None:
        """Treat Ruff parse diagnostics as findings rather than operational failures."""
        path = self.write("example.py", "def broken(\n")
        assert check_ruff([path])

    def test_no_files_does_not_scan_the_current_directory(self) -> None:
        """Avoid Ruff's implicit directory scan when the input set is empty."""
        self.write("example.py", "import os\n")
        with mock.patch("pyunslop.ruff_runner.subprocess.run") as run:
            assert check_ruff([]) == []
        run.assert_not_called()

    def test_cli_runs_ruff_and_still_exits_successfully(self) -> None:
        """Run the real module entry point with findings from both engines."""
        source = "import os\nvalue=1\n"
        path = self.write("example.py", source)
        result = subprocess.run([sys.executable, "-m", "pyunslop"], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
        assert "warning: F401" in result.stdout
        assert "warning: RFMT001" in result.stdout
        assert path.read_text() == source

    def test_operational_failure_does_not_report_success(self) -> None:
        """Distinguish an unavailable Ruff engine from ordinary lint findings."""
        path = self.write("example.py", "value = 1\n")
        failed = subprocess.CompletedProcess([], 2, "", "Ruff unavailable")
        message = ""

        # Nonzero exits without diagnostics must not be mistaken for ordinary findings.
        with mock.patch("pyunslop.ruff_runner.subprocess.run", return_value=failed):
            try:
                check_ruff([path])
            except RuntimeError as error:
                message = str(error)
        assert "Ruff unavailable" in message

    def test_bundled_preset_matches_development_configuration(self) -> None:
        """Keep the wheel's preset synchronized with the requested pyproject tables."""
        preset = files("pyunslop").joinpath("ruff.toml").read_text(encoding="utf-8")
        project = Path(__file__).resolve().parents[1].joinpath("pyproject.toml").read_text(encoding="utf-8")
        expected = "[tool.ruff]\n" + preset.replace("\n[", "\n[tool.ruff.")
        assert project.endswith(expected)


if __name__ == "__main__":
    unittest.main()
