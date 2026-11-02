import pytest
from tests.support import RunCLI, native_codes

CANDIDATES = (
    pytest.param("total = 0\n" + "total += 1\n" * 12, 11, id="first-budget-crossing-only"),
    pytest.param("total = 0\n" * 9 + "if total:\n    total += 1\n", 10, id="weighted-header"),
    pytest.param("for item in items:\n    if item.enabled:\n" + "        work()\n" * 6, 8, id="nested-header"),
    pytest.param("total = 0  # Initialize\n" * 10 + "\ntotal += 1\n", 12, id="inline-comments-and-blanks-do-not-reset"),
    pytest.param("values = [\n" + "    load(),\n" * 12 + "]\n", 11, id="computed-container"),
)


@pytest.mark.parametrize(("source", "line"), CANDIDATES)
def test_reports_first_complexity_crossing(run_cli: RunCLI, source: str, line: int) -> None:
    """Report the documented ten-point boundary at its original source line."""

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP001"]
    assert f"example.py:{line}:1: SLOP001" in result.stdout


EXEMPTIONS = (
    pytest.param("total = sum(monthly_totals)\n", id="documented-simplification"),
    pytest.param("value = 1\n" * 10, id="exact-budget"),
    pytest.param("value = 1\n" * 10 + "\n# Explain the next phase.\n" + "value = 2\n" * 10, id="standalone-comment-reset"),
    pytest.param("value = 1\n" * 10 + "\n\ndef work():\n" + "    pass\n" * 9, id="function-reset"),
    # Data layout and multiline signatures do not add executable work.
    pytest.param("values = [\n" + "    [1, (-2, None)],\n" * 15 + "]\n" + "value = 1\n" * 9, id="literal-container"),
    pytest.param(
        "def work(\n" + "".join(f"    arg{index}: int = {index},\n" for index in range(15)) + ") -> None:\n" + "    pass\n" * 9,
        id="multiline-signature",
    ),
    pytest.param('text = """first\n' + "second\n" * 15 + 'third"""\n', id="multiline-string"),
    pytest.param("from pathlib import Path\n" * 12 + "value = 1\n" * 10, id="imports-excluded"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_budget_resets_and_collapsed_data(run_cli: RunCLI, source: str) -> None:
    """Keep documented non-candidates free of native findings."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
