import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize("method", ["execute", "scalars", "stream", "stream_scalars"])
def test_requires_a_name_before_consuming_async_results(run_cli: RunCLI, method: str) -> None:
    """Recognize result-returning query APIs through real CLI analysis."""

    # Arrange
    source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    return (await session.{method}(statement)).all()\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP004"]


EXEMPTIONS = (
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    result = await session.execute(statement)\n    return result.all()\n",
        id="named-result",
    ),
    pytest.param("async def fetch(session):\n    return (await session.execute(statement)).all()\n", id="unknown-session"),
    # Scalar values and shadowed imports must not acquire result provenance.
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(session: AsyncSession):\n    return (await session.scalar(statement)).value\n",
        id="scalar-value-api",
    ),
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession as Session\nasync def fetch(Session):\n    return (await Session.execute(statement)).all()\n",
        id="shadowed-import",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_named_unknown_and_scalar_values(run_cli: RunCLI, source: str) -> None:
    """Do not infer query results from names alone or scalar-valued APIs."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
