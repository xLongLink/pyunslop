import pytest
from tests.support import RunCLI, CheckNative, native_codes

CANDIDATES = (
    pytest.param("return bool(result.all())", id="direct-bool"),
    pytest.param("return len(result.all()) > 3", id="length-threshold"),
    pytest.param("if result.all():\n        return True\n    return False", id="truth-test"),
    pytest.param("rows = result.all()\n    return len(rows) >= threshold", id="named-size-only-rows"),
)


@pytest.mark.parametrize("body", CANDIDATES)
def test_reports_size_only_row_loading(run_cli: RunCLI, body: str) -> None:
    """Recognize direct and named materialization used solely for size or truth."""

    # Arrange
    source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def has_users(session: AsyncSession):\n    result = await session.execute(statement)\n    {body}\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP019"]
    assert "preserve locking" in result.stdout


EXEMPTIONS = (
    # Existence queries avoid row loading; data consumers require the loaded rows.
    pytest.param(
        "from sqlalchemy import select\nfrom sqlalchemy.ext.asyncio import AsyncSession\nasync def has_users(session: AsyncSession):\n    statement = select(select(User.id).exists())\n    return bool(await session.scalar(statement))\n",
        id="existence-query",
    ),
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.scalars(statement)\n    rows = result.all()\n    consume(rows)\n    return len(rows)\n",
        id="rows-consumed-as-data",
    ),
    # Unknown results and closure references cannot establish size-only consumption.
    pytest.param("def has_users(result):\n    return bool(result.all())\n", id="unknown-result"),
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.scalars(statement)\n    rows = result.all()\n    def later():\n        return rows\n    return len(rows), later\n",
        id="closure-reuses-data",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_data_consumers_and_existence_queries(run_cli: RunCLI, source: str) -> None:
    """Only size-only use authorizes a query review candidate."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


def test_nested_size_only_load_does_not_inherit_outer_data_use(check_native: CheckNative) -> None:
    """Find nested size-only rows even when the outer function consumes its rows as data."""
    source = "from sqlalchemy.engine import Result\ndef outer(result: Result):\n    rows = result.all()\n    consume(rows)\n    async def inner(result: Result):\n        rows = result.all()\n        return bool(rows)\n    return inner\n"

    # Act
    findings = check_native(source)

    # Assert
    assert [(finding.code, finding.line) for finding in findings] == [("SLOP019", 6)]
