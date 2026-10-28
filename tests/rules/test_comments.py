import ast
import sys
import pytest
from pyunslop import Warning as CheckWarning
from collections.abc import Callable
from pyunslop.rules.comments import control_weights

MULTILINE_STRINGS = (
    'text = """first\n' + "second\n" * 15 + 'third"""\n',
    'text = ("first"\n' + '        "second"\n' * 15 + '        "third")\n',
)


SUPPRESSION_DIRECTIVES = (
    "# noqa",
    "#noqa: F401",
    "# NoQa: F401, F841",
    "# noqa: SLOP003",
    # File-wide forms are also forbidden inside inline comment tokens.
    "# ruff: noqa",
    "# flake8: noqa: F401",
    "# RUFF:noqa: F401",
    "#\tnoqa",
)


def test_frequency_reports_once_per_run_at_threshold(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Report the first line beyond the fixed ten-point budget."""
    warnings = check_source("a = 1\n" * 13)
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 11)]


@pytest.mark.parametrize(
    ("opening", "item", "closing"), [("[", "1,", "]"), ("(", "-1,", ")"), ("{", "'name',", "}"), ("{", "'name': [1, (-2, None)],", "}")]
)
def test_literal_containers_cost_one_point(
    check_source: Callable[[str], list[CheckWarning]], opening: str, item: str, closing: str
) -> None:
    """Ignore data layout while retaining the container's initial point."""
    source = f"VALUES = {opening}\n" + f"    {item}\n" * 15 + closing + "\n"
    assert check_source(source + "work()\n" * 9) == []
    warnings = check_source(source + "work()\n" * 10)
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 27)]


@pytest.mark.parametrize("item", ["load(),", "value,", "1 + 2,", "*items,", "f'{value}',"])
def test_executable_collections_are_not_collapsed(check_source: Callable[[str], list[CheckWarning]], item: str) -> None:
    """Do not hide runtime expressions inside collection syntax."""
    warnings = check_source("VALUES = [\n" + f"    {item}\n" * 12 + "]\n")
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 11)]


@pytest.mark.parametrize("expression", ["[\n    item\n    for item in items\n]", "{\n    **mapping,\n}"])
def test_comprehensions_and_dict_unpacking_still_count(check_source: Callable[[str], list[CheckWarning]], expression: str) -> None:
    """Retain every executable continuation line."""
    warnings = check_source("work()\n" * 9 + f"VALUES = {expression}\n")
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 11)]


def test_literal_end_line_keeps_executable_tokens(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Honor token boundaries, including non-ASCII AST column offsets."""
    source = "work()\n" * 9 + "é = [\n    1,\n]; work()\n"
    warnings = check_source(source)
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 12)]


@pytest.mark.parametrize("header", ["if ready:", "for item in items:", "while ready:", "with resource:"])
def test_control_headers_cost_two_points(check_source: Callable[[str], list[CheckWarning]], header: str) -> None:
    """Warn when a header jumps from nine points to eleven."""
    warnings = check_source("work()\n" * 9 + header + "\n    work()\n")
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 10)]


def test_nesting_weights_only_control_headers(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Charge two for the loop, three for the branch, and one per call."""
    source = "for item in items:\n    if item.enabled:\n" + "        work()\n" * 6
    warnings = check_source(source)
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 8)]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("try:\n    work()\nexcept Error:\n    recover()\n", {1: 2, 3: 3}),
        ("match item:\n    case 1:\n        work()\n    case _:\n        pass\n", {1: 2, 2: 3, 4: 3}),
        ("async def run():\n    async with resource:\n        async for item in items:\n            pass\n", {2: 2, 3: 3}),
        ("for a in items:\n    while ready:\n        if enabled:\n            work()\n", {1: 2, 2: 3, 3: 4}),
        ("if first:\n    pass\nelif second:\n    pass\n", {1: 2, 3: 3}),
        ("if ready: work()\n", {1: 2}),
    ],
)
def test_control_header_weights(source: str, expected: dict[int, int]) -> None:
    """Cover branching, async headers, sibling cases, and deeper nesting."""
    assert control_weights(ast.parse(source)) == expected


@pytest.mark.skipif(sys.version_info < (3, 11), reason="except* requires Python 3.11")
def test_exception_group_headers() -> None:
    """Apply the same weights to exception-group handlers."""
    assert control_weights(ast.parse("try:\n    work()\nexcept* Error:\n    recover()\n")) == {1: 2, 3: 3}


@pytest.mark.parametrize("header", ["def run():", "async def run():"])
def test_nested_functions_do_not_inherit_control_depth(check_source: Callable[[str], list[CheckWarning]], header: str) -> None:
    """Reset the budget and nesting when entering a nested function."""
    source = "if outer:\n    " + header + "\n        if inner:\n" + "            work()\n" * 7
    assert check_source(source) == []
    warnings = check_source(source + "            work()\n")
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 11)]


def test_comment_resets_points_but_not_control_depth(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Retain nesting after an explanation resets the accumulated budget."""
    source = "for item in items:\n    # Explain this branch.\n    if ready:\n" + "        work()\n" * 8
    warnings = check_source(source)
    assert [(w.code, w.line) for w in warnings] == [("SLOP002", 2), ("SLOP001", 11)]


def test_imports_and_blank_lines_do_not_count(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Exclude multiline imports and whitespace from the code-line limit."""
    source = "import os\nfrom pathlib import (\n    Path,\n)\n\n" + "x = 1\n" * 10
    assert check_source(source) == []


def test_inline_comments_do_not_reset_frequency(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Require standalone comments rather than trailing annotations."""
    warnings = check_source("a = 1  # First\n" * 10 + "\nb = 2\n")
    assert [(w.code, w.line) for w in warnings] == [("SLOP001", 12)]


def test_standalone_comments_reset_frequency(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Start a new code-line run after a standalone comment."""
    source = "a = 1\n" * 10 + "\n# Explain the next step.\n" + "b = 2\n" * 10
    assert check_source(source) == []


def test_function_definitions_reset_frequency(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Reset frequency at synchronous and asynchronous function boundaries."""
    source = "a = 1\n" * 10 + "def run():\n" + "    pass\n" * 9
    source += "async def other():\n" + "    pass\n" * 9
    assert check_source(source) == []


@pytest.mark.parametrize("prefix", ["def", "async def"])
def test_multiline_signatures_count_once(check_source: Callable[[str], list[CheckWarning]], prefix: str) -> None:
    """Do not require comments merely because parameters span many lines."""
    signature = f"{prefix} run(\n" + "".join(f"    arg{index}: int = {index},\n" for index in range(15)) + ") -> None:\n"
    assert check_source(signature + "    work()\n" * 9) == []
    warnings = check_source(signature + "    work()\n" * 10)
    assert [(warning.code, warning.line) for warning in warnings] == [("SLOP001", 27)]


def test_signature_closing_line_keeps_inline_body(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Retain executable code sharing the signature's closing line."""
    signature = "def run(\n    value: int,\n): "
    assert check_source(signature + "; ".join("work()" for _ in range(10)) + "\n") == []
    warnings = check_source(signature + "work()\n" + "work()\n" * 9)
    assert [(warning.code, warning.line) for warning in warnings] == [("SLOP001", 12)]


def test_first_body_decorators_still_count(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Do not mistake decorators on a nested definition for signature lines."""
    source = "def outer(\n    value: int,\n):\n" + "    @decorate\n" * 10 + "    def inner():\n        pass\n"
    assert [(warning.code, warning.line) for warning in check_source(source)] == [("SLOP001", 13)]


@pytest.mark.parametrize("source", MULTILINE_STRINGS)
def test_multiline_and_adjacent_strings_count_once(check_source: Callable[[str], list[CheckWarning]], source: str) -> None:
    """Avoid counting every physical line of a string expression."""
    assert check_source(source) == []


def test_comment_block_requires_one_blank_line(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Report only the start of an unseparated comment block."""
    warnings = check_source("x = 1\n# First\n# Second\ny = 2\n")
    assert [(w.code, w.line) for w in warnings] == [("SLOP002", 2)]


def test_suite_comments_require_separation_but_continuations_are_exempt(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Require suite separation without flagging bracketed expression comments."""
    source = "if True:\n    # Explain this branch.\n    values = [\n        # Explain this value.\n        1,\n    ]\n"
    assert [(warning.code, warning.line) for warning in check_source(source)] == [("SLOP002", 2)]


def test_loop_comment_requires_separation(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Require a blank line before a loop's opening comment."""
    source = "for path in paths:\n    # Explicit files bypass exclusions.\n    if path.is_file():\n        candidates = [path]\n"
    assert [(warning.code, warning.line) for warning in check_source(source)] == [("SLOP002", 2)]
    assert check_source(source.replace("paths:\n", "paths:\n\n")) == []


def test_first_line_and_separated_comments_are_allowed(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Allow file headings and comment blocks after blank lines."""
    assert check_source("# Heading\nx = 1\n\n# Next step\ny = 2\n") == []


def test_comment_spacing_is_left_to_ruff(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Leave inline and block comment spacing to Ruff E262/E265."""
    assert check_source("#!/usr/bin/env python3\n#\nx = 1  #bad\n\n#bad\n## heading\n") == []


@pytest.mark.parametrize("directive", SUPPRESSION_DIRECTIVES)
def test_noqa_directive_variants(check_source: Callable[[str], list[CheckWarning]], directive: str) -> None:
    """Reject inline, blanket, code-specific, and file-wide suppressions."""
    findings = [warning for warning in check_source(f"value = 1  {directive}\n") if warning.code == "SLOP003"]
    assert [(warning.line, warning.column) for warning in findings] == [(1, 12)]
    assert findings[0].message == "noqa suppression directives are forbidden"


def test_noqa_locations_inside_comments(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Locate the directive itself after indentation or explanatory text."""
    source = "if ready:\n    value = 1  # explanation # noqa: F401\n"
    warnings = check_source(source)
    assert [(warning.code, warning.line, warning.column) for warning in warnings] == [("SLOP003", 2, 30)]


def test_noqa_strings_and_ordinary_comments_are_ignored(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Do not treat string examples, prose, or longer words as directives."""
    source = 'text = "# noqa: F401"\ntext = """# ruff: noqa\n# flake8: noqa"""\n\n# Explain noqa conventions.\n# noqaish\n# ruff: noqaish\n'
    assert check_source(source) == []


def test_hashes_in_strings_are_not_comments(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Distinguish hash characters in strings from comment tokens."""
    assert check_source('text = "#not a comment"\n') == []
