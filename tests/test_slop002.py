import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize("statement", ["users = fetch_users()", 'value = ":"'])
def test_reports_only_the_opening_comment(run_cli: RunCLI, statement: str) -> None:
    """Require separation after statements, including those containing colons."""

    # Arrange
    source = statement + "\n# Keep active accounts.\n# Preserve their order.\nactive = users\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP002"]
    assert "example.py:2:1: SLOP002" in result.stdout


EXEMPTIONS = (
    pytest.param("users = fetch_users()\n\n# Keep active accounts.\nactive = users\n", id="separated-block"),
    pytest.param("# File heading\nvalue = 1\n", id="file-heading"),
    # Opening suite comments follow logical headers, including multiline ones.
    pytest.param("if ready:\n    # Explain branch.\n    pass\n", id="if-suite"),
    pytest.param("for item in items:\n    # Explain iteration.\n    consume(item)\n", id="for-suite"),
    pytest.param("if ready:\n    pass\nelse:\n    # Explain fallback.\n    pass\n", id="else-suite"),
    pytest.param("def work(\n    value: int,\n):\n    # Explain body.\n    return value\n", id="multiline-suite-header"),
    pytest.param("values = [\n    # Keep the sentinel first.\n    1,\n]\n", id="bracket-continuation"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_accepts_documented_comment_exemptions(run_cli: RunCLI, source: str) -> None:
    """Match suite and continuation exemptions without changing source files."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
