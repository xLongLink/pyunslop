import pytest
from tests.support import RunCLI, native_codes

CANDIDATES = (
    pytest.param(
        'from sqlalchemy import column\ncondition = column("user_id").in_([member.user_id for member in members])\n', id="sqlalchemy-column"
    ),
    pytest.param(
        "from sqlmodel import col as column\ncondition = column(User.id).in_([member.user_id for member in members])\n", id="sqlmodel-alias"
    ),
    # A known statement can establish ownership without a column constructor.
    pytest.param(
        "from sqlalchemy import select\nstatement = select(User)\nstatement = statement.where(User.id.in_([member.id for member in members]))\n",
        id="known-query-context",
    ),
)


@pytest.mark.parametrize("source", CANDIDATES)
def test_reports_list_comprehensions_in_sql_membership(run_cli: RunCLI, source: str) -> None:
    """Recognize SQL expression ownership rather than method spelling alone."""

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP008"]


EXEMPTIONS = (
    pytest.param(
        'from sqlalchemy import column\ncondition = column("user_id").in_(member.user_id for member in members)\n', id="generator"
    ),
    pytest.param(
        'from sqlalchemy import column\nids = [member.user_id for member in members]\ncondition = column("user_id").in_(ids)\n',
        id="existing-list",
    ),
    # SQL context must not propagate through unrelated calls.
    pytest.param("condition = custom.in_([member.user_id for member in members])\n", id="unrelated-method"),
    pytest.param(
        "from sqlalchemy import select\nstatement = select(User).where(custom.consume(custom.in_([item.id for item in items])))\n",
        id="unrelated-nested-call",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_accepts_generators_existing_lists_and_unrelated_methods(run_cli: RunCLI, source: str) -> None:
    """Preserve non-candidates even when enclosed by a SQL query."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
