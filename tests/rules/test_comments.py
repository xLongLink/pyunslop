import pytest
from pyunslop import Warning as CheckWarning
from collections.abc import Callable

MULTILINE_STRINGS = (
    'text = """first\n' + "second\n" * 15 + 'third"""\n',
    'text = ("first"\n' + '        "second"\n' * 15 + '        "third")\n',
)


SUPPRESSION_DIRECTIVES = (
    "# noqa",
    "#noqa: F401",
    "# NoQa: F401, F841",
    "# noqa: CM004",
    # File-wide forms are also forbidden inside inline comment tokens.
    "# ruff: noqa",
    "# flake8: noqa: F401",
    "# RUFF:noqa: F401",
    "#\tnoqa",
)


def test_frequency_reports_once_per_run_at_threshold(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Report the first line beyond the fixed ten-line limit."""
    warnings = check_source("a = 1\n" * 13)
    assert [(w.code, w.line) for w in warnings] == [("CM001", 11)]


def test_imports_and_blank_lines_do_not_count(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Exclude multiline imports and whitespace from the code-line limit."""
    source = "import os\nfrom pathlib import (\n    Path,\n)\n\n" + "x = 1\n" * 10
    assert check_source(source) == []


def test_inline_comments_do_not_reset_frequency(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Require standalone comments rather than trailing annotations."""
    warnings = check_source("a = 1  # First\n" * 10 + "\nb = 2\n")
    assert [(w.code, w.line) for w in warnings] == [("CM001", 12)]


def test_standalone_comments_reset_frequency(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Start a new code-line run after a standalone comment."""
    source = "a = 1\n" * 10 + "\n# Explain the next step.\n" + "b = 2\n" * 10
    assert check_source(source) == []


def test_function_definitions_reset_frequency(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Reset frequency at synchronous and asynchronous function boundaries."""
    source = "a = 1\n" * 10 + "def run():\n" + "    pass\n" * 9
    source += "async def other():\n" + "    pass\n" * 9
    assert check_source(source) == []


@pytest.mark.parametrize("source", MULTILINE_STRINGS)
def test_multiline_and_adjacent_strings_count_once(check_source: Callable[[str], list[CheckWarning]], source: str) -> None:
    """Avoid counting every physical line of a string expression."""
    assert check_source(source) == []


def test_comment_block_requires_one_blank_line(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Report only the start of an unseparated comment block."""
    warnings = check_source("x = 1\n# First\n# Second\ny = 2\n")
    assert [(w.code, w.line) for w in warnings] == [("CM002", 2)]


def test_suite_and_continuation_comments_need_no_blank_line(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Exempt suite starts and comments inside continued expressions."""
    source = "if True:\n    # Explain this branch.\n    values = [\n        # Explain this value.\n        1,\n    ]\n"
    assert check_source(source) == []


def test_first_line_and_separated_comments_are_allowed(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Allow file headings and comment blocks after blank lines."""
    assert check_source("# Heading\nx = 1\n\n# Next step\ny = 2\n") == []


def test_comment_spacing_and_locations(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Keep shebang exemptions and one-based comment locations."""
    warnings = check_source("#!/usr/bin/env python3\n#\nx = 1  #bad\n\n#bad\n")
    assert [(w.code, w.line, w.column) for w in warnings] == [("CM003", 3, 8), ("CM003", 5, 1)]
    assert ":3:8: warning: CM003 " in str(warnings[0])


@pytest.mark.parametrize("directive", SUPPRESSION_DIRECTIVES)
def test_noqa_directive_variants(check_source: Callable[[str], list[CheckWarning]], directive: str) -> None:
    """Reject inline, blanket, code-specific, and file-wide suppressions."""
    findings = [warning for warning in check_source(f"value = 1  {directive}\n") if warning.code == "CM004"]
    assert [(warning.line, warning.column) for warning in findings] == [(1, 12)]
    assert findings[0].message == "noqa suppression directives are forbidden"


def test_noqa_locations_inside_comments(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Locate the directive itself after indentation or explanatory text."""
    source = "if ready:\n    value = 1  # explanation # noqa: F401\n"
    warnings = check_source(source)
    assert [(warning.code, warning.line, warning.column) for warning in warnings] == [("CM004", 2, 30)]


def test_noqa_strings_and_ordinary_comments_are_ignored(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Do not treat string examples, prose, or longer words as directives."""
    source = 'text = "# noqa: F401"\ntext = """# ruff: noqa\n# flake8: noqa"""\n\n# Explain noqa conventions.\n# noqaish\n# ruff: noqaish\n'
    assert check_source(source) == []


def test_hashes_in_strings_are_not_comments(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Distinguish hash characters in strings from comment tokens."""
    assert check_source('text = "#not a comment"\n') == []
