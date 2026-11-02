import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize("consumer", ["one", "one_or_none", "all"])
def test_reports_execute_scalars_consumption(run_cli: RunCLI, consumer: str) -> None:
    """Keep cardinality guidance when recommending the scalar result API."""

    # Arrange
    source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.execute(statement)\n    return result.scalars().{consumer}()\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP018"]
    assert "preserve one()/one_or_none() cardinality checks" in result.stdout


@pytest.mark.parametrize("body", ["for user, in result:\n        consume(user)", "user, = result.one()\n    return user"])
def test_reports_single_selection_row_unpacking(run_cli: RunCLI, body: str) -> None:
    """Recognize single-selection statements before loop or row unpacking."""

    # Arrange
    source = f"from sqlalchemy import select\nfrom sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.execute(select(User))\n    {body}\n"

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == ["SLOP018"]
    assert "cardinality" in result.stdout


EXEMPTIONS = (
    # Scalar APIs already express the intent; multi-column rows must retain their shape.
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.scalars(statement)\n    return result.one_or_none()\n",
        id="scalar-query-api",
    ),
    pytest.param(
        "from sqlalchemy import select\nfrom sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.execute(select(User.id, User.name))\n    for user_id, name in result:\n        consume(user_id, name)\n",
        id="multiple-selections",
    ),
    # One-element unpacking alone does not establish the query's selection shape.
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.execute(statement)\n    for user, in result:\n        consume(user)\n",
        id="unknown-selection-shape",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_scalar_apis_and_unknown_row_shapes(run_cli: RunCLI, source: str) -> None:
    """Do not simplify multi-column or unknown selections."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
