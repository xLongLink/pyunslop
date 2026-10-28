import tempfile
import unittest
from pathlib import Path

from pyunslop import check_file, find_python_files
from pyunslop import Warning as CheckWarning


class CheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def check(self, source: str) -> list[CheckWarning]:
        path = self.root / "example.py"
        path.write_text(source, encoding="utf-8")
        return check_file(path)

    def test_frequency_reports_once_per_run_at_threshold(self) -> None:
        warnings = self.check("a = 1\n" * 13)
        self.assertEqual([(w.code, w.line) for w in warnings], [("CM001", 11)])

    def test_imports_and_blank_lines_do_not_count(self) -> None:
        source = "import os\nfrom pathlib import (\n    Path,\n)\n\n" + "x = 1\n" * 10
        self.assertEqual(self.check(source), [])

    def test_inline_comments_do_not_reset_frequency(self) -> None:
        warnings = self.check("a = 1  # First\n" * 10 + "\nb = 2\n")
        self.assertEqual([(w.code, w.line) for w in warnings], [("CM001", 12)])

    def test_standalone_comments_reset_frequency(self) -> None:
        source = "a = 1\n" * 10 + "\n# Explain the next step.\n" + "b = 2\n" * 10
        self.assertEqual(self.check(source), [])

    def test_function_definitions_reset_frequency(self) -> None:
        source = "a = 1\n" * 10 + "def run():\n" + "    pass\n" * 9
        source += "async def other():\n" + "    pass\n" * 9
        self.assertEqual(self.check(source), [])

    def test_multiline_and_adjacent_strings_count_once(self) -> None:
        for source in (
            'text = """first\n' + 'second\n' * 15 + 'third"""\n',
            'text = ("first"\n' + '        "second"\n' * 15 + '        "third")\n',
        ):
            with self.subTest(source=source):
                self.assertEqual(self.check(source), [])

    def test_comment_block_requires_one_blank_line(self) -> None:
        warnings = self.check("x = 1\n# First\n# Second\ny = 2\n")
        self.assertEqual([(w.code, w.line) for w in warnings], [("CM002", 2)])

    def test_suite_and_continuation_comments_need_no_blank_line(self) -> None:
        source = "if True:\n    # Explain this branch.\n    values = [\n        # Explain this value.\n        1,\n    ]\n"
        self.assertEqual(self.check(source), [])

    def test_first_line_and_separated_comments_are_allowed(self) -> None:
        self.assertEqual(self.check("# Heading\nx = 1\n\n# Next step\ny = 2\n"), [])

    def test_comment_spacing_and_locations(self) -> None:
        warnings = self.check("#!/usr/bin/env python3\n#\nx = 1  #bad\n\n#bad\n")
        self.assertEqual(
            [(w.code, w.line, w.column) for w in warnings],
            [("CM003", 3, 8), ("CM003", 5, 1)],
        )
        self.assertIn(":3:8: warning: CM003 ", str(warnings[0]))

    def test_hashes_in_strings_are_not_comments(self) -> None:
        self.assertEqual(self.check('text = "#not a comment"\n'), [])

    def test_invalid_source_is_skipped(self) -> None:
        self.assertEqual(self.check("def broken(\n"), [])

    def test_missing_file_is_skipped(self) -> None:
        self.assertEqual(check_file(self.root / "missing.py"), [])

    def test_source_encoding_is_respected(self) -> None:
        path = self.root / "encoded.py"
        path.write_bytes(b'# coding: latin-1\nname = "caf\xe9"\n')
        self.assertEqual(check_file(path), [])

    def test_invalid_encoding_is_skipped(self) -> None:
        path = self.root / "encoded.py"
        path.write_bytes(b"\xff\n")
        self.assertEqual(check_file(path), [])

    def test_limit_cannot_be_overridden(self) -> None:
        with self.assertRaises(TypeError):
            check_file(self.root / "example.py", max_lines=1)

    def test_repository_policies_cannot_be_disabled(self) -> None:
        with self.assertRaises(TypeError):
            check_file(self.root / "example.py", repo_policy=False)

    def test_discovery_excludes_generated_files_and_deduplicates(self) -> None:
        source = self.root / "source.py"
        source.touch()
        (self.root / "notes.txt").touch()
        excluded = self.root / ".venv"
        excluded.mkdir()
        hidden_source = excluded / "dependency.py"
        hidden_source.touch()
        self.assertEqual(list(find_python_files([self.root, source])), [source])
        self.assertEqual(list(find_python_files([hidden_source])), [hidden_source])

    def test_missing_discovery_path_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            list(find_python_files([self.root / "missing"]))


if __name__ == "__main__":
    unittest.main()
