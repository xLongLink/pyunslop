import pytest
from tests.support import RunCLI, CheckNative, native_codes


@pytest.mark.parametrize(
    ("annotation", "expression"),
    [("list[User]", "result.all()"), ("list[User]", "list(result.all())"), ('"MutableList[User]"', "result.all()")],
)
def test_reports_mutable_query_return_contract_once(run_cli: RunCLI, annotation: str, expression: str) -> None:
    """Recognize direct and copied rows, reporting each mutable contract once."""

    # Arrange
    source = f"""
        from typing import List as MutableList
        from sqlalchemy.ext.asyncio import AsyncSession

        async def fetch(session: AsyncSession) -> {annotation}:
            result = await session.scalars(statement)
            if ready:
                return {expression}
            return {expression}
    """

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP005"]
    assert "use Sequence[T]" in result.stdout


EXEMPTIONS = (
    # Sequence contracts and nonquery lists remain outside this rule.
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


@pytest.mark.parametrize(("outer_kind", "inner_kind"), [("def", "async def"), ("async def", "def")])
@pytest.mark.parametrize(("outer_type", "inner_type", "line"), [("Sequence[User]", "list[User]", 4), ("list[User]", "Sequence[User]", 3)])
def test_nested_returns_use_the_nearest_contract(
    check_native: CheckNative, outer_kind: str, inner_kind: str, outer_type: str, inner_type: str, line: int
) -> None:
    """Keep nested return contracts separate and restore the enclosing contract."""
    source = f"from collections.abc import Sequence\nfrom sqlalchemy.engine import Result\n{outer_kind} outer(result: Result) -> {outer_type}:\n    {inner_kind} inner(result: Result) -> {inner_type}:\n        return result.all()\n    return result.all()\n"

    # Act
    findings = check_native(source)

    # Assert
    assert [(finding.code, finding.line) for finding in findings] == [("SLOP005", line)]
