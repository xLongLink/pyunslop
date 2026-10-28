import tempfile
import unittest
from pathlib import Path
from pyunslop import Warning as CheckWarning
from pyunslop import check_file


class CommentTests(unittest.TestCase):
    """Check comment frequency, separation, spacing, and suppressions."""

    def setUp(self) -> None:
        """Create an isolated directory for source fixtures."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def check(self, source: str) -> list[CheckWarning]:
        """Write a fixture and return native warnings for its exact source."""
        path = self.root / "example.py"
        path.write_text(source, encoding="utf-8")
        return check_file(path)

    def test_frequency_reports_once_per_run_at_threshold(self) -> None:
        """Report the first line beyond the fixed ten-line limit."""
        warnings = self.check("a = 1\n" * 13)
        assert [(w.code, w.line) for w in warnings] == [("CM001", 11)]

    def test_imports_and_blank_lines_do_not_count(self) -> None:
        """Exclude multiline imports and whitespace from the code-line limit."""
        source = "import os\nfrom pathlib import (\n    Path,\n)\n\n" + "x = 1\n" * 10
        assert self.check(source) == []

    def test_inline_comments_do_not_reset_frequency(self) -> None:
        """Require standalone comments rather than trailing annotations."""
        warnings = self.check("a = 1  # First\n" * 10 + "\nb = 2\n")
        assert [(w.code, w.line) for w in warnings] == [("CM001", 12)]

    def test_standalone_comments_reset_frequency(self) -> None:
        """Start a new code-line run after a standalone comment."""
        source = "a = 1\n" * 10 + "\n# Explain the next step.\n" + "b = 2\n" * 10
        assert self.check(source) == []

    def test_function_definitions_reset_frequency(self) -> None:
        """Reset frequency at synchronous and asynchronous function boundaries."""
        source = "a = 1\n" * 10 + "def run():\n" + "    pass\n" * 9
        source += "async def other():\n" + "    pass\n" * 9
        assert self.check(source) == []

    def test_multiline_and_adjacent_strings_count_once(self) -> None:
        """Avoid counting every physical line of a string expression."""
        for source in (
            'text = """first\n' + "second\n" * 15 + 'third"""\n',
            'text = ("first"\n' + '        "second"\n' * 15 + '        "third")\n',
        ):
            with self.subTest(source=source):
                assert self.check(source) == []

    def test_comment_block_requires_one_blank_line(self) -> None:
        """Report only the start of an unseparated comment block."""
        warnings = self.check("x = 1\n# First\n# Second\ny = 2\n")
        assert [(w.code, w.line) for w in warnings] == [("CM002", 2)]

    def test_suite_and_continuation_comments_need_no_blank_line(self) -> None:
        """Exempt suite starts and comments inside continued expressions."""
        source = "if True:\n    # Explain this branch.\n    values = [\n        # Explain this value.\n        1,\n    ]\n"
        assert self.check(source) == []

    def test_first_line_and_separated_comments_are_allowed(self) -> None:
        """Allow file headings and comment blocks after blank lines."""
        assert self.check("# Heading\nx = 1\n\n# Next step\ny = 2\n") == []

    def test_comment_spacing_and_locations(self) -> None:
        """Keep shebang exemptions and one-based comment locations."""
        warnings = self.check("#!/usr/bin/env python3\n#\nx = 1  #bad\n\n#bad\n")
        assert [(w.code, w.line, w.column) for w in warnings] == [("CM003", 3, 8), ("CM003", 5, 1)]
        assert ":3:8: warning: CM003 " in str(warnings[0])

    def test_noqa_directive_variants(self) -> None:
        """Reject inline, blanket, code-specific, and file-wide suppressions."""
        for directive in (
            "# noqa",
            "#noqa: F401",
            "# NoQa: F401, F841",
            "# noqa: CM004",
            # File-wide forms are also forbidden inside inline comment tokens.
            "# ruff: noqa",
            "# flake8: noqa: F401",
            "# RUFF:noqa: F401",
            "#\tnoqa",
        ):
            with self.subTest(directive=directive):
                findings = [warning for warning in self.check(f"value = 1  {directive}\n") if warning.code == "CM004"]
                assert [(warning.line, warning.column) for warning in findings] == [(1, 12)]
                assert findings[0].message == "noqa suppression directives are forbidden"

    def test_noqa_locations_inside_comments(self) -> None:
        """Locate the directive itself after indentation or explanatory text."""
        source = "if ready:\n    value = 1  # explanation # noqa: F401\n"
        warnings = self.check(source)
        assert [(warning.code, warning.line, warning.column) for warning in warnings] == [("CM004", 2, 30)]

    def test_noqa_strings_and_ordinary_comments_are_ignored(self) -> None:
        """Do not treat string examples, prose, or longer words as directives."""
        source = (
            'text = "# noqa: F401"\ntext = """# ruff: noqa\n# flake8: noqa"""\n\n# Explain noqa conventions.\n# noqaish\n# ruff: noqaish\n'
        )
        assert self.check(source) == []

    def test_hashes_in_strings_are_not_comments(self) -> None:
        """Distinguish hash characters in strings from comment tokens."""
        assert self.check('text = "#not a comment"\n') == []
