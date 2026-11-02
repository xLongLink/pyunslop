import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize("expression", ["result.all()", "list(result.all())"])
def test_reports_mutable_query_return_contract(run_cli: RunCLI, expression: str) -> None:
    """Recommend Sequence for direct rows and list-wrapped query returns."""

    # Arrange
    source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession) -> list[User]:\n    result = await session.scalars(statement)\n    return {expression}\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP005"]
    assert "use Sequence[T]" in result.stdout


def test_reports_aliased_quoted_list_contract_once(run_cli: RunCLI) -> None:
    """Multiple offending returns still produce one return-contract diagnostic."""

    # Arrange
    source = """
        from typing import List as MutableList
        from sqlalchemy.ext.asyncio import AsyncSession

        async def fetch(session: AsyncSession) -> "MutableList[User]":
            result = await session.scalars(statement)
            if ready:
                return result.all()
            return result.all()
    """

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == ["SLOP005"]


EXEMPTIONS = (
    pytest.param(
        "from collections.abc import Sequence\nfrom sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession) -> Sequence[User]:\n    result = await session.scalars(statement)\n    return result.all()\n",
        id="sequence-contract",
    ),
    pytest.param("def build() -> list[int]:\n    return [1, 2, 3]\n", id="ordinary-mutable-list"),
    pytest.param("def fetch(result) -> list[User]:\n    return result.all()\n", id="unknown-result"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_sequence_and_nonquery_contracts(run_cli: RunCLI, source: str) -> None:
    """Only recognized query-row returns impose read-only guidance."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
