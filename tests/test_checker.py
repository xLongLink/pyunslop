import tempfile
import unittest
from pathlib import Path
from pyunslop import Warning as CheckWarning
from pyunslop import check_file, find_python_files


class CheckerTests(unittest.TestCase):
    """Check comment boundaries, source handling, and file discovery."""

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

    def test_hashes_in_strings_are_not_comments(self) -> None:
        """Distinguish hash characters in strings from comment tokens."""
        assert self.check('text = "#not a comment"\n') == []

    def test_invalid_source_is_skipped(self) -> None:
        """Skip source that cannot be parsed by the native checks."""
        assert self.check("def broken(\n") == []

    def test_missing_file_is_skipped(self) -> None:
        """Skip an individual file that disappears before inspection."""
        assert check_file(self.root / "missing.py") == []

    def test_source_encoding_is_respected(self) -> None:
        """Honor a Python source encoding declaration when reading bytes."""
        path = self.root / "encoded.py"
        path.write_bytes(b'# coding: latin-1\nname = "caf\xe9"\n')
        assert check_file(path) == []

    def test_invalid_encoding_is_skipped(self) -> None:
        """Skip undecodable source without raising an inspection error."""
        path = self.root / "encoded.py"
        path.write_bytes(b"\xff\n")
        assert check_file(path) == []

    def test_limit_cannot_be_overridden(self) -> None:
        """Reject per-call overrides of the fixed comment limit."""
        error: TypeError | None = None
        try:
            check_file(self.root / "example.py", max_lines=1)
        except TypeError as exc:
            error = exc
        assert error is not None

    def test_repository_policies_cannot_be_disabled(self) -> None:
        """Reject per-call attempts to disable repository policies."""
        error: TypeError | None = None
        try:
            check_file(self.root / "example.py", repo_policy=False)
        except TypeError as exc:
            error = exc
        assert error is not None

    def test_discovery_excludes_generated_files_and_deduplicates(self) -> None:
        """Skip generated directories unless an explicit file path requests them."""
        source = self.root / "source.py"
        source.touch()
        (self.root / "notes.txt").touch()
        excluded = self.root / ".venv"
        excluded.mkdir()
        hidden_source = excluded / "dependency.py"
        hidden_source.touch()

        # Act / Assert: overlapping project paths must not duplicate source files.
        assert list(find_python_files([self.root, source])) == [source]
        assert list(find_python_files([hidden_source])) == [hidden_source]

    def test_missing_discovery_path_raises(self) -> None:
        """Report a missing discovery root rather than silently skipping it."""
        error: FileNotFoundError | None = None
        try:
            list(find_python_files([self.root / "missing"]))
        except FileNotFoundError as exc:
            error = exc
        assert error is not None


if __name__ == "__main__":
    unittest.main()
