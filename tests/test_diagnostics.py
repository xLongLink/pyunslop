import ast
import unittest
from pathlib import Path
from pyunslop.diagnostics import Finding
from pyunslop.diagnostics import Warning as CheckWarning


class DiagnosticTests(unittest.TestCase):
    """Check diagnostic locations and the editor-facing output contract."""

    def test_ast_columns_are_converted_to_one_based_locations(self) -> None:
        """Preserve indented statement locations when constructing findings."""

        # Arrange
        node = ast.parse("if ready:\n    value = 1\n").body[0].body[0]

        # Act
        finding = Finding.at(node, "PY001", "Explain the issue")

        # Assert
        assert finding == Finding(2, 5, "PY001", "Explain the issue")

    def test_warning_format_contains_path_location_code_and_message(self) -> None:
        """Retain the complete diagnostic in an editor-friendly representation."""

        # Arrange
        warning = CheckWarning(Path("nested/example.py"), 2, 5, "PY001", "Explain the issue")

        # Act
        rendered = str(warning)

        # Assert
        assert rendered == "nested/example.py:2:5: warning: PY001 Explain the issue"
